"""Análise exploratória com NumPy, Matplotlib e Seaborn."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

FAMILY_ORDER = [
    "cpu", "gpu", "motherboard", "ram", "storage", "power_supply", "case", "cooling", "peripherals",
]


def save(fig, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    reviews_path = args.data_dir / "processed" / "parquet" / "reviews.parquet"
    products_path = args.data_dir / "processed" / "parquet" / "products.parquet"
    if not reviews_path.exists():
        raise SystemExit("Execute scripts/treat_and_report.py antes da EDA.")
    run_report_path = args.data_dir / "processed" / "run_report.json"
    if not run_report_path.exists():
        raise SystemExit(f"Relatório de aquisição não encontrado: {run_report_path}.")
    run_report = json.loads(run_report_path.read_text(encoding="utf-8"))
    run_id = run_report.get("run_id")
    source_mode = run_report.get("source", {}).get("mode", "unknown")
    figures = args.output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="notebook", font="DejaVu Sans")
    reviews = pd.read_parquet(reviews_path)
    products = pd.read_parquet(products_path)
    ratings = reviews["review_rating"].to_numpy(dtype=float)
    sentiment = reviews["sentiment_score"].to_numpy(dtype=float)
    text_len = reviews["text_length"].to_numpy(dtype=float)
    prices = products["price_usd"].to_numpy(dtype=float)

    summary = {
        "run_id": run_id,
        "source_mode": source_mode,
        "reviews": int(len(reviews)),
        "products": int(len(products)),
        "rating_mean": float(np.nanmean(ratings)),
        "rating_std": float(np.nanstd(ratings)),
        "rating_percentiles": {
            "p10": float(np.nanpercentile(ratings, 10)),
            "p50": float(np.nanpercentile(ratings, 50)),
            "p90": float(np.nanpercentile(ratings, 90)),
        },
        "positive_rate": float(np.mean(reviews["is_positive"].to_numpy())),
        "verified_rate": float(np.mean(reviews["verified_purchase"].to_numpy())),
        "price_missing_pct": float(np.mean(products["price_missing"].to_numpy()) * 100),
        "price_median_observed": float(np.nanmedian(prices)) if np.isfinite(prices).any() else None,
        "sentiment_mean": float(np.nanmean(sentiment)),
        "text_length_mean": float(np.nanmean(text_len)),
        "review_year_min": int(reviews["review_year"].min()),
        "review_year_max": int(reviews["review_year"].max()),
        "rating_counts": {
            str(rating): int(count)
            for rating, count in reviews["review_rating"].value_counts().sort_index().items()
        },
        "family_review_counts": {
            str(family): int(count)
            for family, count in reviews["component_family"].value_counts().sort_index().items()
        },
        "imbalance_ratio_pos_neg": float(
            np.sum(reviews["is_positive"] == 1) / max(np.sum(reviews["is_positive"] == 0), 1)
        ),
    }
    (args.output_dir / "eda_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    sns.countplot(data=reviews, x="review_rating", color="#0f4c81", ax=ax)
    ax.set_xlabel("Nota da avaliação")
    ax.set_ylabel("Quantidade")
    ax.set_title("Distribuição das notas (desbalanceamento)")
    save(fig, figures / "01_rating_distribution.png")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    order = [f for f in FAMILY_ORDER if f in set(reviews["component_family"])]
    sns.countplot(data=reviews, y="component_family", order=order, color="#c45c26", ax=ax)
    ax.set_xlabel("Avaliações")
    ax.set_ylabel("Família")
    ax.set_title("Volume de avaliações por família de componente")
    save(fig, figures / "02_volume_by_family.png")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    observed = products.dropna(subset=["price_usd"])
    sns.boxplot(data=observed, x="component_family", y="price_usd", order=order, ax=ax, color="#7a8b99")
    ax.set_yscale("log")
    ax.set_xlabel("Família")
    ax.set_ylabel("Preço observado (USD, log)")
    ax.set_title("Preço snapshot por família — não é série temporal")
    plt.xticks(rotation=25, ha="right")
    save(fig, figures / "03_price_by_family.png")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    period = reviews[reviews["period"].isin(["old", "recent"])]
    sns.barplot(data=period, x="component_family", y="review_rating", hue="period", order=order, ax=ax, errorbar=None)
    ax.set_xlabel("Família")
    ax.set_ylabel("Nota média")
    ax.set_title("Nota média: período antigo versus recente")
    plt.xticks(rotation=25, ha="right")
    save(fig, figures / "04_rating_old_recent.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    year_counts = reviews.groupby("review_year").size()
    ax.plot(year_counts.index.to_numpy(), year_counts.to_numpy(), color="#14202b", linewidth=2.2)
    ax.set_xlabel("Ano")
    ax.set_ylabel("Avaliações")
    ax.set_title("Volume de avaliações ao longo do tempo")
    save(fig, figures / "05_volume_by_year.png")

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    missing = pd.DataFrame({
        "campo": ["price_usd", "brand_unknown", "review_text_vazio", "helpful_votes_zero"],
        "percentual": [
            float(products["price_missing"].mean() * 100),
            float((products["brand"] == "unknown").mean() * 100),
            float((reviews["text_length"] == 0).mean() * 100),
            float((reviews["helpful_votes"] == 0).mean() * 100),
        ],
    })
    sns.barplot(data=missing, x="percentual", y="campo", color="#5b6e7a", ax=ax)
    ax.set_xlabel("% de registros")
    ax.set_ylabel("")
    ax.set_title("Cobertura: faltantes e valores sentinela")
    save(fig, figures / "06_missingness.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.boxplot(data=reviews, x="is_positive", y="sentiment_score", ax=ax, color="#0f4c81")
    ax.set_xticks([0, 1], ["não positiva (<4)", "positiva (≥4)"])
    ax.set_ylabel("Score léxico de sentimento")
    ax.set_xlabel("")
    ax.set_title("Sentimento textual versus classe-alvo")
    save(fig, figures / "07_sentiment_by_class.png")

    product_ratings = reviews.groupby("product_id").agg(
        review_mean=("review_rating", "mean"),
        review_count=("review_rating", "size"),
    ).reset_index()
    price_rating = products.merge(product_ratings, on="product_id", how="inner")
    price_rating = price_rating.dropna(subset=["price_usd", "review_mean"])
    price_rating = price_rating[price_rating["price_usd"] > 0]
    fig, ax = plt.subplots(figsize=(10, 6))
    if not price_rating.empty:
        sns.scatterplot(
            data=price_rating,
            x="price_usd",
            y="review_mean",
            hue="component_family",
            alpha=0.7,
            ax=ax,
        )
        ax.set_xscale("log")
        ax.legend(
            title="Família",
            bbox_to_anchor=(1.02, 1),
            loc="upper left",
            borderaxespad=0,
            fontsize=8,
            title_fontsize=9,
        )
    ax.set_xlabel("Preço observado do produto (USD, escala log)")
    ax.set_ylabel("Nota média das avaliações no corpus")
    ax.set_title("Preço observado versus nota média por produto")
    ax.set_ylim(0.8, 5.2)
    if source_mode == "sample":
        ax.text(
            0.01, 0.02, "Demonstração sintética — não representa a fonte real",
            transform=ax.transAxes, color="#8b1e1e", fontsize=9,
        )
    fig.tight_layout(rect=(0, 0, 0.83, 1))
    fig.savefig(figures / "08_price_rating_association.png", dpi=220)
    plt.close(fig)

    missing.to_csv(args.output_dir / "quality_summary.csv", index=False)
    print(json.dumps(summary, indent=2))
    print(f"Figuras em {figures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
