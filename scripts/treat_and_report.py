#!/usr/bin/env python3
"""Tratamento e relatórios do dataset InfTechs.

Gera inventário de campos, dados tratados e comparações entre períodos antigos
(e.g. avaliações mais antigas) e recentes. O preço dos metadados Amazon 2023 é
um snapshot; comparação temporal de preços só é feita quando --historical-prices
fornece um CSV com product_id, observed_at e price_usd.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as source:
        for line_no, line in enumerate(source, 1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def flatten(value) -> str:
    if isinstance(value, dict):
        return " ".join(f"{k} {flatten(v)}" for k, v in value.items())
    if isinstance(value, list):
        return " ".join(flatten(v) for v in value)
    return str(value or "")


def clean_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def safe_year(timestamp):
    try:
        return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).year
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def pct(value):
    return round(float(value) * 100, 2) if value is not None and not math.isnan(value) else None


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def inventory(records: list[dict], name: str) -> dict:
    fields = Counter()
    for record in records:
        fields.update(record.keys())
    return {
        "dataset": name,
        "records": len(records),
        "fields": [{"name": field, "records_present": count, "coverage_pct": round(count / max(len(records), 1) * 100, 2)} for field, count in sorted(fields.items())],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    parser.add_argument("--historical-prices", type=Path, default=None, help="CSV opcional: product_id,observed_at,price_usd")
    args = parser.parse_args()
    processed = args.data_dir / "processed"
    products_path = processed / "products.jsonl"
    reviews_path = processed / "reviews.jsonl"
    if not products_path.exists() or not reviews_path.exists():
        raise SystemExit(f"Arquivos tratados ainda não encontrados: {products_path} e {reviews_path}. Aguarde a aquisição/filtragem terminar.")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    products = list(read_jsonl(products_path))
    reviews_raw = list(read_jsonl(reviews_path))
    products_by_id = {str(p.get("parent_asin")): p for p in products if p.get("parent_asin")}

    clean_products = []
    for p in products:
        product_id = str(p.get("parent_asin") or "").strip()
        if not product_id:
            continue
        details = p.get("details") if isinstance(p.get("details"), dict) else {}
        brand = clean_text(details.get("Brand") or p.get("store")) or "unknown"
        price = p.get("price")
        try:
            price = float(price) if price is not None else None
        except (TypeError, ValueError):
            price = None
        clean_products.append({
            "product_id": product_id,
            "product_title": clean_text(p.get("title")),
            "brand": brand,
            "component_family": p.get("component_family") or "unknown",
            "price_usd": price,
            "average_rating": p.get("average_rating"),
            "rating_number": p.get("rating_number"),
            "feature_text": clean_text(flatten(p.get("features"))),
            "description_text": clean_text(flatten(p.get("description"))),
            "categories_text": clean_text(flatten(p.get("categories"))),
        })

    clean_reviews = []
    for r in reviews_raw:
        parent = str(r.get("parent_asin") or "").strip()
        if not parent or parent not in products_by_id:
            continue
        text = clean_text(r.get("text"))
        title = clean_text(r.get("title"))
        try:
            rating = float(r.get("rating"))
        except (TypeError, ValueError):
            continue
        if not 1 <= rating <= 5:
            continue
        year = safe_year(r.get("timestamp"))
        product = products_by_id[parent]
        clean_reviews.append({
            "product_id": parent,
            "variant_id": r.get("asin"),
            "user_id": r.get("user_id"),
            "component_family": product.get("component_family") or "unknown",
            "review_rating": rating,
            "review_title": title,
            "review_text": text,
            "review_year": year,
            "verified_purchase": bool(r.get("verified_purchase")),
            "helpful_votes": int(r.get("helpful_votes") or 0),
            "text_length": len(text),
        })

    products_df = pd.DataFrame(clean_products)
    reviews_df = pd.DataFrame(clean_reviews)
    if reviews_df.empty:
        raise SystemExit("Nenhuma avaliação válida foi encontrada após o tratamento.")
    valid_years = reviews_df["review_year"].dropna().astype(int)
    if valid_years.empty:
        raise SystemExit("Não foi possível derivar anos válidos das avaliações.")
    low_cut = float(valid_years.quantile(0.2))
    high_cut = float(valid_years.quantile(0.8))
    reviews_df["period"] = reviews_df["review_year"].apply(lambda y: "old" if y <= low_cut else ("recent" if y >= high_cut else "middle"))

    products_df.to_csv(args.output_dir / "products_clean.csv", index=False)
    reviews_df.to_csv(args.output_dir / "reviews_clean.csv", index=False)

    group_rows = []
    for (family, period), group in reviews_df.groupby(["component_family", "period"], dropna=False):
        group_rows.append({
            "component_family": family,
            "period": period,
            "reviews": len(group),
            "avg_rating": round(group["review_rating"].mean(), 4),
            "median_rating": round(group["review_rating"].median(), 4),
            "verified_pct": round(group["verified_purchase"].mean() * 100, 2),
            "avg_helpful_votes": round(group["helpful_votes"].mean(), 4),
            "avg_text_length": round(group["text_length"].mean(), 2),
            "first_year": int(group["review_year"].min()),
            "last_year": int(group["review_year"].max()),
        })
    comparison = pd.DataFrame(group_rows)
    comparison.to_csv(args.output_dir / "comparison_old_recent_reviews.csv", index=False)

    pivot = comparison.pivot(index="component_family", columns="period", values="avg_rating") if not comparison.empty else pd.DataFrame()
    if not pivot.empty:
        pivot["rating_change_recent_minus_old"] = pivot.get("recent") - pivot.get("old")
        pivot.reset_index().to_csv(args.output_dir / "rating_change_by_family.csv", index=False)

    price_summary = products_df.groupby("component_family", dropna=False).agg(
        products=("product_id", "nunique"),
        avg_price_usd=("price_usd", "mean"),
        median_price_usd=("price_usd", "median"),
        avg_rating_snapshot=("average_rating", "mean"),
    ).reset_index()
    price_summary.to_csv(args.output_dir / "price_snapshot_by_family.csv", index=False)

    price_note = "Preço atual não comparado temporalmente: a fonte fornece um snapshot por produto."
    if args.historical_prices and args.historical_prices.exists():
        hp = pd.read_csv(args.historical_prices, parse_dates=["observed_at"])
        hp = hp.dropna(subset=["product_id", "observed_at", "price_usd"])
        hp["period"] = hp.groupby("product_id")["observed_at"].transform(lambda s: s.rank(method="first").map(lambda x: "old" if x == 1 else ("recent" if x == s.notna().sum() else "middle")))
        old = hp[hp.period == "old"].rename(columns={"price_usd": "old_price_usd"})[["product_id", "old_price_usd"]]
        recent = hp[hp.period == "recent"].rename(columns={"price_usd": "recent_price_usd"})[["product_id", "recent_price_usd"]]
        price_changes = old.merge(recent, on="product_id")
        price_changes["price_change_usd"] = price_changes["recent_price_usd"] - price_changes["old_price_usd"]
        price_changes["price_change_pct"] = price_changes["price_change_usd"] / price_changes["old_price_usd"].replace(0, pd.NA) * 100
        price_changes.to_csv(args.output_dir / "price_change_old_recent.csv", index=False)
        price_note = f"Comparação de preço feita com o histórico adicional {args.historical_prices}."

    fields_report = {
        "products": inventory(products, "products_raw"),
        "reviews": inventory(reviews_raw, "reviews_raw"),
        "treated": {"products": len(products_df), "reviews": len(reviews_df)},
        "period_definition": {"old_max_year_quantile_20": low_cut, "recent_min_year_quantile_80": high_cut},
        "price_interpretation": price_note,
    }
    (args.output_dir / "data_inventory.json").write_text(json.dumps(fields_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6))
    plot_df = comparison[comparison["period"].isin(["old", "recent"])].pivot(index="component_family", columns="period", values="avg_rating")
    plot_df.plot(kind="bar", ax=ax, color={"old": "#6b7280", "recent": "#2563eb"})
    ax.set_title("Nota média: período antigo versus período recente")
    ax.set_xlabel("Família de componente")
    ax.set_ylabel("Nota média (1–5)")
    ax.legend(title="Período")
    fig.tight_layout()
    fig.savefig(args.output_dir / "rating_old_recent.png", dpi=160)
    plt.close(fig)

    report_lines = [
        "# Relatório de tratamento e comparação temporal",
        "",
        f"Foram tratados **{len(products_df):,} produtos** e **{len(reviews_df):,} avaliações válidas**.",
        f"O período antigo corresponde às avaliações até aproximadamente o quantil de 20% (ano máximo: **{int(low_cut)}**) e o período recente às avaliações a partir do quantil de 80% (ano mínimo: **{int(high_cut)}**).",
        "",
        "## Arquivos gerados",
        "",
        "- `data_inventory.json`: campos disponíveis, cobertura e contagens.",
        "- `comparison_old_recent_reviews.csv`: notas, verificações, votos úteis e tamanho textual por família e período.",
        "- `rating_change_by_family.csv`: diferença entre nota recente e antiga por família.",
        "- `price_snapshot_by_family.csv`: comparação de preço observado por família, sem afirmar evolução temporal.",
        "- `rating_old_recent.png`: gráfico de comparação das notas.",
        "",
        "## Interpretação dos preços",
        "",
        f"> {price_note}",
        "",
        "Para comparar preço antigo e atual de forma válida, forneça um arquivo CSV com snapshots repetidos por produto e as colunas `product_id`, `observed_at` e `price_usd` usando `--historical-prices`.",
    ]
    (args.output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Relatórios gerados em {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
