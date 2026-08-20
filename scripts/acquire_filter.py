#!/usr/bin/env python3
"""Acquire and filter Amazon Reviews 2023 Electronics for InfTechs.

Raw downloads stay under data/raw (ignored by git). The processed JSONL is capped
by target bytes and selected deterministically by parent_asin hash.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw"
REVIEW_URL = f"{BASE}/review_categories/Electronics.jsonl.gz"
META_URL = f"{BASE}/meta_categories/meta_Electronics.jsonl.gz"

KEYWORDS = {
    "cpu": ["cpu", "processor", "ryzen", "core i3", "core i5", "core i7", "core i9", "threadripper", "xeon"],
    "gpu": ["graphics card", "video card", "gpu", "geforce", "rtx", "gtx", "radeon", "rx 5", "rx 6", "rx 7"],
    "motherboard": ["motherboard", "mainboard", "b450", "b550", "x570", "z690", "z790", "am4", "am5", "lga 1200", "lga 1700"],
    "ram": ["memory ram", "desktop memory", "ddr3", "ddr4", "ddr5", "sodimm", "dimm"],
    "storage": ["solid state drive", "ssd", "hard drive", "hdd", "nvme", "m.2 drive", "internal drive"],
    "power_supply": ["power supply", "psu", "atx power", "modular power supply", "80 plus"],
    "case": ["computer case", "pc case", "tower case", "chassis", "desktop case"],
    "cooling": ["cpu cooler", "liquid cooler", "water cooling", "heatsink", "computer fan", "case fan"],
    "peripherals": ["computer keyboard", "gaming keyboard", "computer mouse", "gaming mouse", "webcam", "monitor", "computer speaker"],
}


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        print(f"[download] usando arquivo existente: {destination} ({destination.stat().st_size:,} bytes)", flush=True)
        return
    print(f"[download] iniciando {url}", flush=True)
    request = Request(url, headers={"User-Agent": "InfTechs-academic-pipeline/1.0"})
    with urlopen(request, timeout=60) as response, destination.open("wb") as output:
        total = int(response.headers.get("Content-Length") or 0)
        received = 0
        started = time.time()
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            received += len(chunk)
            if received % (100 * 1024 * 1024) < len(chunk):
                rate = received / max(time.time() - started, 1)
                print(f"[download] {received / 1024**3:.2f} GiB" + (f" / {total / 1024**3:.2f} GiB" if total else "") + f" ({rate / 1024**2:.1f} MiB/s)", flush=True)
    print(f"[download] concluído: {destination} ({received:,} bytes)", flush=True)


def flatten(value) -> str:
    if isinstance(value, dict):
        return " ".join(f"{k} {flatten(v)}" for k, v in value.items())
    if isinstance(value, list):
        return " ".join(flatten(v) for v in value)
    return str(value or "")


def classify(item: dict) -> str | None:
    text = " ".join([
        str(item.get("title") or ""),
        flatten(item.get("features")),
        flatten(item.get("description")),
        flatten(item.get("details")),
        flatten(item.get("categories")),
    ]).lower()
    text = re.sub(r"\s+", " ", text)
    for family, terms in KEYWORDS.items():
        if any(term in text for term in terms):
            return family
    return None


def stable_selected(product_id: str, fraction: float) -> bool:
    digest = hashlib.sha256(product_id.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / 16**16 < fraction


def write_jsonl(path: Path, records) -> tuple[int, int]:
    count = size = 0
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            output.write(line)
            count += 1
            size += len(line.encode("utf-8"))
    return count, size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--target-gib", default=1.0, type=float)
    parser.add_argument("--selection-fraction", default=1.0, type=float)
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    raw = args.data_dir / "raw"
    processed = args.data_dir / "processed"
    raw.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    meta_path = raw / "meta_Electronics.jsonl.gz"
    review_path = raw / "Electronics.jsonl.gz"
    if not args.skip_download:
        download(META_URL, meta_path)
        download(REVIEW_URL, review_path)

    selected: dict[str, dict] = {}
    with gzip.open(meta_path, "rt", encoding="utf-8") as source:
        for line_no, line in enumerate(source, 1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            parent = item.get("parent_asin")
            family = classify(item)
            if parent and family and stable_selected(parent, args.selection_fraction):
                selected.setdefault(parent, {**item, "component_family": family})
            if line_no % 100_000 == 0:
                print(f"[metadata] linhas={line_no:,} produtos_selecionados={len(selected):,}", flush=True)
    print(f"[metadata] produtos selecionados={len(selected):,}", flush=True)

    meta_out = processed / "products.jsonl"
    with meta_out.open("w", encoding="utf-8") as output:
        for item in selected.values():
            output.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")

    target_bytes = int(args.target_gib * 1024**3)
    review_out = processed / "reviews.jsonl"
    written_bytes = meta_out.stat().st_size
    review_count = 0
    review_bytes = 0
    with gzip.open(review_path, "rt", encoding="utf-8") as source, review_out.open("w", encoding="utf-8") as output:
        for line_no, line in enumerate(source, 1):
            try:
                review = json.loads(line)
            except json.JSONDecodeError:
                continue
            parent = review.get("parent_asin")
            if parent not in selected:
                continue
            review["component_family"] = selected[parent]["component_family"]
            encoded = (json.dumps(review, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            if written_bytes + len(encoded) > target_bytes:
                break
            output.write(encoded.decode("utf-8"))
            written_bytes += len(encoded)
            review_count += 1
            review_bytes += len(encoded)
            if line_no % 500_000 == 0:
                print(f"[reviews] linhas={line_no:,} avaliações_selecionadas={review_count:,} tamanho={written_bytes / 1024**3:.2f} GiB", flush=True)
    report = {
        "source": {"metadata_url": META_URL, "review_url": REVIEW_URL},
        "target_gib": args.target_gib,
        "selection_fraction": args.selection_fraction,
        "products_selected": len(selected),
        "reviews_selected": review_count,
        "metadata_bytes": meta_out.stat().st_size,
        "reviews_bytes": review_bytes,
        "total_processed_bytes": written_bytes,
        "generated_at_unix": int(time.time()),
    }
    (processed / "run_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
