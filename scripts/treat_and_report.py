"""Limpeza, imputação, rejeitos, Parquet e comparações temporais de notas."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd

from inftechs_lib import (
    clean_text,
    flatten,
    inventory,
    read_jsonl,
    safe_timestamp,
    safe_year,
    sentiment_score,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    parser.add_argument("--historical-prices", type=Path, default=None)
    args = parser.parse_args()
    processed = args.data_dir / "processed"
    products_path = processed / "products.jsonl"
    reviews_path = processed / "reviews.jsonl"
    run_report_path = processed / "run_report.json"
    if not products_path.exists() or not reviews_path.exists():
        raise SystemExit(f"Arquivos tratados ainda não encontrados: {products_path} e {reviews_path}.")
    if not run_report_path.exists():
        raise SystemExit(f"Relatório de aquisição não encontrado: {run_report_path}.")
    run_report = json.loads(run_report_path.read_text(encoding="utf-8"))
    run_id = run_report.get("run_id")
    source_mode = run_report.get("source", {}).get("mode", "unknown")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figures = args.output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    products = list(read_jsonl(products_path))
    reviews_raw = list(read_jsonl(reviews_path))
    rejections = []

    clean_products = []
    seen_products = set()
    for idx, p in enumerate(products, 1):
        product_id = str(p.get("parent_asin") or "").strip()
        if not product_id:
            rejections.append({"entity": "product", "line": idx, "reason": "missing_parent_asin"})
            continue
        if product_id in seen_products:
            rejections.append({"entity": "product", "line": idx, "reason": "duplicate_parent_asin", "product_id": product_id})
            continue
        seen_products.add(product_id)
        details = p.get("details") if isinstance(p.get("details"), dict) else {}
        brand = clean_text(details.get("Brand") or p.get("store")) or "unknown"
        price = p.get("price")
        try:
            price = float(price) if price is not None and str(price).strip() != "" else np.nan
        except (TypeError, ValueError):
            rejections.append({"entity": "product", "line": idx, "reason": "invalid_price", "product_id": product_id})
            price = np.nan
        if pd.notna(price) and price < 0:
            rejections.append({"entity": "product", "line": idx, "reason": "negative_price", "product_id": product_id})
            price = np.nan
        clean_products.append({
            "product_id": product_id,
            "product_title": clean_text(p.get("title")),
            "brand": brand.lower(),
            "component_family": p.get("component_family") or "unknown",
            "price_usd": price,
            "average_rating": p.get("average_rating"),
            "rating_number": p.get("rating_number"),
            "feature_text": clean_text(flatten(p.get("features"))),
            "description_text": clean_text(flatten(p.get("description"))),
            "categories_text": clean_text(flatten(p.get("categories"))),
        })

    products_df = pd.DataFrame(clean_products)
    products_df["price_missing"] = products_df["price_usd"].isna().astype(int)
    family_median = products_df.groupby("component_family")["price_usd"].transform("median")
    global_median = float(np.nanmedian(products_df["price_usd"].to_numpy(dtype=float))) if products_df["price_usd"].notna().any() else 0.0
    products_df["price_usd_imputed"] = products_df["price_usd"].fillna(family_median).fillna(global_median)
    products_df["brand"] = products_df["brand"].replace("", "unknown").fillna("unknown")
    products_by_id = products_df.set_index("product_id").to_dict("index")

    clean_reviews = []
    seen_reviews = set()
    for idx, r in enumerate(reviews_raw, 1):
        parent = str(r.get("parent_asin") or "").strip()
        if not parent:
            rejections.append({"entity": "review", "line": idx, "reason": "missing_parent_asin"})
            continue
        if parent not in products_by_id:
            rejections.append({"entity": "review", "line": idx, "reason": "product_not_found", "product_id": parent})
            continue
        text = clean_text(r.get("text"))
        title = clean_text(r.get("title"))
        try:
            rating = float(r.get("rating"))
        except (TypeError, ValueError):
            rejections.append({"entity": "review", "line": idx, "reason": "invalid_rating", "product_id": parent})
            continue
        if not 1 <= rating <= 5:
            rejections.append({"entity": "review", "line": idx, "reason": "rating_out_of_range", "product_id": parent})
            continue
        ts = safe_timestamp(r.get("timestamp"))
        if ts is None:
            ts_ms = r.get("timestamp")
            try:
                ts = safe_timestamp(float(ts_ms) / 1000.0)
            except (TypeError, ValueError):
                ts = None
        year = ts.year if ts is not None else safe_year(r.get("timestamp"))
        if year is None:
            rejections.append({"entity": "review", "line": idx, "reason": "invalid_timestamp", "product_id": parent})
            continue
        user_id = str(r.get("user_id") or "")
        key = (parent, user_id, text, year, rating)
        if key in seen_reviews:
            rejections.append({"entity": "review", "line": idx, "reason": "duplicate_review", "product_id": parent})
            continue
        seen_reviews.add(key)
        product = products_by_id[parent]
        helpful = r.get("helpful_votes")
        try:
            helpful = int(helpful) if helpful is not None else 0
        except (TypeError, ValueError):
            helpful = 0
        clean_reviews.append({
            "product_id": parent,
            "variant_id": r.get("asin"),
            "user_id": user_id,
            "component_family": product.get("component_family") or "unknown",
            "brand": product.get("brand") or "unknown",
            "price_usd": product.get("price_usd"),
            "price_usd_imputed": product.get("price_usd_imputed"),
            "price_missing": product.get("price_missing"),
            "review_rating": rating,
            "review_title": title,
            "review_text": text,
            "review_year": int(year),
            "review_timestamp": ts.isoformat() if ts else None,
            "verified_purchase": int(bool(r.get("verified_purchase"))),
            "helpful_votes": helpful,
            "text_length": len(text),
            "sentiment_score": round(sentiment_score(f"{title} {text}"), 4),
            "is_positive": int(rating >= 4),
        })

    reviews_df = pd.DataFrame(clean_reviews)
    if reviews_df.empty:
        raise SystemExit("Nenhuma avaliação válida foi encontrada após o tratamento.")

    train_prices = products_df.loc[products_df["price_usd"].notna(), "price_usd"]
    if len(train_prices) >= 3:
        q33, q66 = np.nanquantile(train_prices.to_numpy(dtype=float), [0.33, 0.66])
    else:
        q33, q66 = 50.0, 150.0

    def price_band(value):
        if pd.isna(value):
            return "unknown"
        if value <= q33:
            return "low"
        if value <= q66:
            return "mid"
        return "high"

    products_df["price_band"] = products_df["price_usd_imputed"].map(price_band)
    reviews_df = reviews_df.merge(products_df[["product_id", "price_band"]], on="product_id", how="left")

    valid_years = reviews_df["review_year"].dropna().astype(int)
    low_cut = float(np.quantile(valid_years.to_numpy(), 0.2))
    high_cut = float(np.quantile(valid_years.to_numpy(), 0.8))
    reviews_df["period"] = np.where(
        reviews_df["review_year"] <= low_cut,
        "old",
        np.where(reviews_df["review_year"] >= high_cut, "recent", "middle"),
    )

    parquet_dir = processed / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    products_df.to_parquet(parquet_dir / "products.parquet", index=False)
    reviews_df.to_parquet(parquet_dir / "reviews.parquet", index=False)
    for family, group in reviews_df.groupby("component_family"):
        family_dir = parquet_dir / "reviews_by_family" / str(family)
        family_dir.mkdir(parents=True, exist_ok=True)
        group.to_parquet(family_dir / "part.parquet", index=False)

    products_df.head(400).to_csv(args.output_dir / "products_sample.csv", index=False)
    reviews_df.head(800).to_csv(args.output_dir / "reviews_sample.csv", index=False)
    pd.DataFrame(rejections).to_csv(args.output_dir / "rejections.csv", index=False)

    group_rows = []
    for (family, period), group in reviews_df.groupby(["component_family", "period"], dropna=False):
        group_rows.append({
            "component_family": family,
            "period": period,
            "reviews": int(len(group)),
            "avg_rating": round(float(group["review_rating"].mean()), 4),
            "median_rating": round(float(group["review_rating"].median()), 4),
            "verified_pct": round(float(group["verified_purchase"].mean()) * 100, 2),
            "avg_helpful_votes": round(float(group["helpful_votes"].mean()), 4),
            "avg_text_length": round(float(group["text_length"].mean()), 2),
            "positive_pct": round(float(group["is_positive"].mean()) * 100, 2),
            "first_year": int(group["review_year"].min()),
            "last_year": int(group["review_year"].max()),
        })
    comparison = pd.DataFrame(group_rows)
    comparison.to_csv(args.output_dir / "comparison_old_recent_reviews.csv", index=False)

    if not comparison.empty:
        pivot = comparison.pivot(index="component_family", columns="period", values="avg_rating")
        pivot["rating_change_recent_minus_old"] = pivot.get("recent") - pivot.get("old")
        pivot.reset_index().to_csv(args.output_dir / "rating_change_by_family.csv", index=False)

    price_summary = products_df.groupby("component_family", dropna=False).agg(
        products=("product_id", "nunique"),
        avg_price_usd=("price_usd", "mean"),
        median_price_usd=("price_usd", "median"),
        imputed_price_pct=("price_missing", "mean"),
        avg_rating_snapshot=("average_rating", "mean"),
    ).reset_index()
    price_summary["imputed_price_pct"] = (price_summary["imputed_price_pct"] * 100).round(2)
    price_summary.to_csv(args.output_dir / "price_snapshot_by_family.csv", index=False)

    price_note = "Preço atual não comparado temporalmente: a fonte fornece um snapshot por produto."
    inflation = None
    if args.historical_prices and args.historical_prices.exists():
        hp = pd.read_csv(args.historical_prices, parse_dates=["observed_at"])
        hp = hp.dropna(subset=["product_id", "observed_at", "price_usd"])
        hp["period"] = hp.groupby("product_id")["observed_at"].transform(
            lambda s: s.rank(method="first").map(lambda x: "old" if x == 1 else ("recent" if x == s.notna().sum() else "middle"))
        )
        old = hp[hp.period == "old"].rename(columns={"price_usd": "old_price_usd"})[["product_id", "old_price_usd"]]
        recent = hp[hp.period == "recent"].rename(columns={"price_usd": "recent_price_usd"})[["product_id", "recent_price_usd"]]
        price_changes = old.merge(recent, on="product_id")
        price_changes["price_change_usd"] = price_changes["recent_price_usd"] - price_changes["old_price_usd"]
        price_changes["price_change_pct"] = price_changes["price_change_usd"] / price_changes["old_price_usd"].replace(0, pd.NA) * 100
        price_changes.to_csv(args.output_dir / "price_change_old_recent.csv", index=False)
        inflation = float(price_changes["price_change_pct"].median()) if not price_changes.empty else None
        price_note = f"Comparação de preço feita com o histórico adicional {args.historical_prices}."

    missing_report = {
        "products_price_missing_pct": round(float(products_df["price_missing"].mean()) * 100, 2),
        "reviews_text_empty_pct": round(float((reviews_df["text_length"] == 0).mean()) * 100, 2),
        "imputation": "Mediana de preço por família; fallback para mediana global. Marca vazia vira unknown. Votos úteis nulos viram 0.",
        "positive_class_pct": round(float(reviews_df["is_positive"].mean()) * 100, 2),
        "rating_counts": reviews_df["review_rating"].value_counts().sort_index().to_dict(),
        "rejections": int(len(rejections)),
        "rejection_reasons": pd.DataFrame(rejections)["reason"].value_counts().to_dict() if rejections else {},
    }

    fields_report = {
        "run_id": run_id,
        "source_mode": source_mode,
        "products": inventory(products, "products_raw"),
        "reviews": inventory(reviews_raw, "reviews_raw"),
        "treated": {"products": int(len(products_df)), "reviews": int(len(reviews_df))},
        "period_definition": {"old_max_year_quantile_20": low_cut, "recent_min_year_quantile_80": high_cut},
        "price_interpretation": price_note,
        "quality": missing_report,
        "inflation_estimate_pct": inflation,
    }
    (args.output_dir / "data_inventory.json").write_text(json.dumps(fields_report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    dashboard = {
        "dataset_version": run_id or "inftechs-treated-unknown",
        "run_id": run_id,
        "source_mode": source_mode,
        "source": "Amazon Reviews 2023",
        "report_status": "ready",
        "products": int(len(products_df)),
        "reviews": int(len(reviews_df)),
        "positive_pct": missing_report["positive_class_pct"],
        "price_missing_pct": missing_report["products_price_missing_pct"],
        "rejections": int(len(rejections)),
        "price_note": price_note,
        "inflation_estimate_pct": inflation,
        "families": comparison.to_dict(orient="records"),
        "price_by_family": json.loads(price_summary.to_json(orient="records")),
        "rating_counts": {str(k): int(v) for k, v in missing_report["rating_counts"].items()},
    }
    (args.output_dir / "dashboard.json").write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report_lines = [
        "# Relatório de tratamento",
        "",
        f"Execução: **{run_id or 'não identificada'}** (modo: **{source_mode}**).",
        f"Foram tratados **{len(products_df):,} produtos** e **{len(reviews_df):,} avaliações válidas**.",
        f"Rejeições registradas: **{len(rejections):,}**. Preços ausentes imputados: **{missing_report['products_price_missing_pct']}%**.",
        f"Classe positiva (nota ≥ 4): **{missing_report['positive_class_pct']}%** das avaliações.",
        f"Período antigo até o ano **{int(low_cut)}**; período recente a partir de **{int(high_cut)}**.",
        "",
        "## Interpretação dos preços",
        "",
        f"> {price_note}",
    ]
    (args.output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Relatórios gerados em {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
