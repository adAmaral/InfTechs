"""Executa aquisição → tratamento → EDA → treino → dashboard."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script: str, extra: list[str]) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / script), *extra]
    print(">", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["stream", "files", "sample"], default="stream")
    parser.add_argument("--target-gib", type=float, default=0.25)
    parser.add_argument("--max-meta-lines", type=int, default=250_000)
    parser.add_argument("--max-review-lines", type=int, default=1_500_000)
    parser.add_argument("--max-products", type=int, default=8_000)
    parser.add_argument("--max-reviews", type=int, default=80_000)
    args = parser.parse_args()
    run("acquire_filter.py", [
        "--source", args.source,
        "--target-gib", str(args.target_gib),
        "--max-meta-lines", str(args.max_meta_lines),
        "--max-review-lines", str(args.max_review_lines),
        "--max-products", str(args.max_products),
        "--max-reviews", str(args.max_reviews),
    ])
    run_report_path = ROOT / "data" / "processed" / "run_report.json"
    run_report = json.loads(run_report_path.read_text(encoding="utf-8"))
    actual_mode = run_report.get("source", {}).get("mode")
    if actual_mode != args.source:
        raise SystemExit(
            f"Modo de aquisição divergente: solicitado {args.source}, encontrado {actual_mode}."
        )
    if args.source == "sample":
        print("AVISO: os resultados desta execução são sintéticos e não representam a fonte real.", flush=True)
    run("treat_and_report.py", [])
    run("eda.py", [])
    run("train_models.py", [])
    run("build_dashboard.py", [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
