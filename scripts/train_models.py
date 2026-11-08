"""Compara classificadores para prever a classe de uma avaliação já escrita."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


NUMERIC = ["price_usd", "price_missing", "verified_purchase", "text_length", "review_year"]
CATEGORICAL = ["component_family", "brand_group"]
LABELS = ["não positiva (<4)", "positiva (>=4)"]


def metrics_dict(y_true, y_pred) -> dict:
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "precision_positive": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall_positive": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1_positive": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "f1_macro": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
    }


def split_by_product(df: pd.DataFrame):
    groups = df["product_id"].astype(str)
    if groups.nunique() < 4:
        raise SystemExit("A avaliação por produto exige ao menos quatro produtos distintos.")

    splitter = GroupShuffleSplit(n_splits=30, test_size=0.25, random_state=42)
    labels = df["is_positive"].astype(int)
    for train_idx, test_idx in splitter.split(df, labels, groups):
        y_train = labels.iloc[train_idx]
        y_test = labels.iloc[test_idx]
        if y_train.nunique() == 2 and y_test.nunique() == 2:
            train = df.iloc[train_idx].copy()
            test = df.iloc[test_idx].copy()
            if set(train["product_id"]).isdisjoint(test["product_id"]):
                return train, test
    raise SystemExit(
        "Não foi possível criar partição por produto contendo as duas classes em treino e teste."
    )


def group_brands(train: pd.DataFrame, test: pd.DataFrame):
    top = train["brand"].fillna("unknown").value_counts().head(12).index
    keep = set(top)
    train = train.copy()
    test = test.copy()
    train["brand_group"] = np.where(train["brand"].fillna("unknown").isin(keep), train["brand"], "other")
    test["brand_group"] = np.where(test["brand"].fillna("unknown").isin(keep), test["brand"], "other")
    return train, test, list(top)


def evaluate_by_family(test: pd.DataFrame, y_pred) -> list[dict]:
    rows = []
    evaluated = test.assign(prediction=y_pred)
    for family, group in evaluated.groupby("component_family"):
        if len(group) < 20 or group["is_positive"].nunique() < 2:
            continue
        rows.append({
            "component_family": family,
            "n": int(len(group)),
            **metrics_dict(group["is_positive"], group["prediction"]),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    parser.add_argument("--max-rows", type=int, default=120_000)
    args = parser.parse_args()
    processed = args.data_dir / "processed"
    reviews_path = processed / "parquet" / "reviews.parquet"
    run_report_path = processed / "run_report.json"
    if not reviews_path.exists():
        raise SystemExit("Execute scripts/treat_and_report.py antes do treino.")
    if not run_report_path.exists():
        raise SystemExit(f"Relatório de aquisição não encontrado: {run_report_path}.")
    run_report = json.loads(run_report_path.read_text(encoding="utf-8"))
    run_id = run_report.get("run_id")
    source_mode = run_report.get("source", {}).get("mode", "unknown")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    figures = args.output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    models_dir = Path(__file__).resolve().parents[1] / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(reviews_path)
    if len(df) > args.max_rows:
        df = df.sample(args.max_rows, random_state=42)
    df = df.dropna(subset=["is_positive", "product_id", "component_family"]).copy()
    df["is_positive"] = df["is_positive"].astype(int)
    df["model_text"] = (
        df["review_title"].fillna("").astype(str).str.strip()
        + " "
        + df["review_text"].fillna("").astype(str).str.strip()
    ).str.strip()
    train, test = split_by_product(df)
    train, test, top_brands = group_brands(train, test)

    y_train = train["is_positive"].to_numpy()
    y_test = test["is_positive"].to_numpy()
    feature_columns = NUMERIC + CATEGORICAL
    model_columns = feature_columns + ["model_text"]

    structured_preprocess = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), NUMERIC),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]), CATEGORICAL),
        ],
        remainder="drop",
    )
    text_preprocess = ColumnTransformer(
        transformers=[
            ("text", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=20_000, sublinear_tf=True), "model_text"),
        ],
        remainder="drop",
    )

    models = {
        "dummy_most_frequent": DummyClassifier(strategy="most_frequent"),
        "logistic_balanced": Pipeline([
            ("prep", structured_preprocess),
            ("clf", LogisticRegression(max_iter=800, class_weight="balanced", solver="lbfgs")),
        ]),
        "random_forest_balanced": Pipeline([
            ("prep", structured_preprocess),
            ("clf", RandomForestClassifier(
                n_estimators=180,
                max_depth=14,
                min_samples_leaf=4,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )),
        ]),
        "hist_gradient_boosting": Pipeline([
            ("prep", structured_preprocess),
            ("clf", HistGradientBoostingClassifier(max_depth=8, learning_rate=0.08, random_state=42)),
        ]),
        "tfidf_logistic_balanced": Pipeline([
            ("prep", text_preprocess),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs")),
        ]),
    }

    results = []
    predictions = {}
    X_train = train[model_columns]
    X_test = test[model_columns]
    for name, model in models.items():
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        predictions[name] = pred
        row = {"model": name, **metrics_dict(y_test, pred)}
        results.append(row)
        print(name, row, flush=True)

    metrics_df = pd.DataFrame(results).sort_values(
        ["balanced_accuracy", "f1_macro"], ascending=False, kind="stable"
    )
    baseline = metrics_df.loc[metrics_df["model"] == "dummy_most_frequent"].iloc[0]
    candidates = metrics_df[metrics_df["model"] != "dummy_most_frequent"]
    winner_name = str(candidates.iloc[0]["model"])
    winner = models[winner_name]
    winner_pred = predictions[winner_name]
    beats_baseline = bool(
        candidates.iloc[0]["balanced_accuracy"] > baseline["balanced_accuracy"]
    )
    model_path = models_dir / "best_model.joblib"
    if beats_baseline:
        joblib.dump(winner, model_path)
    elif model_path.exists():
        model_path.unlink()

    cm = confusion_matrix(y_test, winner_pred, labels=[0, 1])
    report = classification_report(
        y_test, winner_pred, labels=[0, 1], target_names=LABELS, zero_division=0,
    )
    by_family = evaluate_by_family(test, winner_pred)
    product_overlap = set(train["product_id"]) & set(test["product_id"])
    if product_overlap:
        raise RuntimeError("A partição de teste compartilha produtos com o treino.")

    justification = {
        "task": "Classificar como positiva (nota >= 4) ou não positiva uma avaliação cujo texto já está disponível.",
        "prediction_scope": "Classificação da avaliação após sua publicação; não é recomendação nem previsão pré-compra.",
        "split": "Holdout aleatório agrupado por product_id (75%/25% aproximado); nenhum produto aparece nos dois conjuntos.",
        "features": "Modelos estruturados usam preço original com imputação ajustada no treino, indicador de preço ausente, família, marca, compra verificada, tamanho do texto e ano. TF-IDF usa título e texto da avaliação.",
        "imbalance": (
            f"Taxa positiva no treino={float(np.mean(y_train)):.3f}, "
            f"teste={float(np.mean(y_test)):.3f}. Regressão logística e floresta usam "
            "class_weight=balanced; comparação usa acurácia balanceada e F1 macro, "
            "além do baseline majoritário."
        ),
        "winner": winner_name,
        "beats_baseline": beats_baseline,
        "model_artifact_saved": beats_baseline,
        "why": (
            "Maior acurácia balanceada entre os modelos não triviais, com F1 macro como desempate."
            if beats_baseline else
            "Nenhum modelo superou a acurácia balanceada do baseline; não há evidência de ganho preditivo."
        ),
        "top_brands_from_train": top_brands,
    }

    payload = {
        "run_id": run_id,
        "source_mode": source_mode,
        "n_total": int(len(df)),
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "positive_rate_train": round(float(np.mean(y_train)), 4),
        "positive_rate_test": round(float(np.mean(y_test)), 4),
        "unique_products_train": int(train["product_id"].nunique()),
        "unique_products_test": int(test["product_id"].nunique()),
        "product_overlap": len(product_overlap),
        "metrics": results,
        "winner": winner_name,
        "beats_baseline": beats_baseline,
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "by_family": by_family,
        "justification": justification,
    }
    (args.output_dir / "model_metrics.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    metrics_df.to_csv(args.output_dir / "model_metrics.csv", index=False)
    pd.DataFrame(by_family).to_csv(args.output_dir / "model_metrics_by_family.csv", index=False)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(11, 6))
    plot_df = metrics_df.melt(
        id_vars="model",
        value_vars=["balanced_accuracy", "f1_macro", "precision_positive", "recall_positive"],
        var_name="Métrica",
        value_name="Valor",
    )
    model_labels = {
        "dummy_most_frequent": "Baseline",
        "logistic_balanced": "Logística",
        "random_forest_balanced": "Random Forest",
        "hist_gradient_boosting": "Hist. Gradient Boosting",
        "tfidf_logistic_balanced": "TF-IDF + Logística",
    }
    plot_df["model"] = plot_df["model"].map(model_labels)
    metric_labels = {
        "balanced_accuracy": "Acurácia balanceada",
        "f1_macro": "F1 macro",
        "precision_positive": "Precisão (positiva)",
        "recall_positive": "Revocação (positiva)",
    }
    plot_df["Métrica"] = plot_df["Métrica"].map(metric_labels)
    sns.barplot(data=plot_df, x="model", y="Valor", hue="Métrica", ax=ax)
    ax.set_ylim(0, 1)
    ax.set_xlabel("")
    ax.set_ylabel("Valor")
    ax.set_title("Comparação dos classificadores — teste por produto")
    ax.legend(title="Métrica", loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, frameon=False)
    plt.xticks(rotation=12, ha="right", fontsize=9)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(figures / "09_model_comparison.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues", ax=ax,
        xticklabels=LABELS, yticklabels=LABELS,
    )
    ax.set_xlabel("Previsto")
    ax.set_ylabel("Real")
    ax.set_title(f"Matriz de confusão — {winner_name}")
    fig.tight_layout()
    fig.savefig(figures / "10_confusion_matrix.png", dpi=220)
    plt.close(fig)

    print("Winner:", winner_name, "| beat baseline:", beats_baseline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
