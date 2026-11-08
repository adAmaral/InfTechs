"""Aquisição e filtragem Amazon Reviews 2023 Electronics para o InfTechs.

Fontes:
  --source stream   lê gzip em fluxo a partir das URLs oficiais (recortes com teto)
  --source files    usa/baixa arquivos em data/raw
  --source sample   gera corpus acadêmico no esquema oficial quando a rede falha
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import io
import json
import os
import random
import time
import sys
import uuid
from contextlib import ExitStack
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inftechs_lib import classify, write_jsonl

BASE = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw"
REVIEW_URL = f"{BASE}/review_categories/Electronics.jsonl.gz"
META_URL = f"{BASE}/meta_categories/meta_Electronics.jsonl.gz"

FAMILIES = [
    "cpu", "gpu", "motherboard", "ram", "storage", "power_supply", "case", "cooling", "peripherals",
]
SAMPLE_TITLES = {
    "cpu": ["AMD Ryzen 5 5600X Processor", "Intel Core i7-12700K CPU"],
    "gpu": ["NVIDIA GeForce RTX 3060 Graphics Card", "AMD Radeon RX 6600 Video Card"],
    "motherboard": ["ASUS TUF Gaming B550-PLUS Motherboard AM4", "MSI MAG Z690 TOMAHAWK LGA 1700"],
    "ram": ["Corsair Vengeance DDR4 Desktop Memory 16GB", "G.Skill Trident Z DDR5 DIMM 32GB"],
    "storage": ["Samsung 970 EVO Plus NVMe SSD 1TB", "Seagate Barracuda Internal Hard Drive 2TB"],
    "power_supply": ["Corsair RM750x 80 Plus Gold Modular Power Supply", "EVGA 600W ATX Power Supply"],
    "case": ["Fractal Design Meshify C ATX PC Case", "NZXT H510 Tower Computer Case"],
    "cooling": ["Noctua NH-D15 CPU Cooler Heatsink", "Arctic Liquid Freezer II Water Cooling"],
    "peripherals": ["Logitech MX Master 3S Computer Mouse", "Keychron K2 Gaming Keyboard"],
}


def stable_selected(product_id: str, fraction: float) -> bool:
    score = stable_hash_score(product_id)
    return score / 16**16 < fraction


def stable_hash_score(product_id: str) -> int:
    return int(hashlib.sha256(product_id.encode("utf-8")).hexdigest()[:16], 16)


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        print(f"[download] usando arquivo existente: {destination} ({destination.stat().st_size:,} bytes)", flush=True)
        return
    print(f"[download] iniciando {url}", flush=True)
    request = Request(url, headers={"User-Agent": "InfTechs-academic-pipeline/1.0"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:
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
                extra = f" / {total / 1024**3:.2f} GiB" if total else ""
                print(f"[download] {received / 1024**3:.2f} GiB{extra} ({rate / 1024**2:.1f} MiB/s)", flush=True)
    print(f"[download] concluído: {destination} ({received:,} bytes)", flush=True)


def open_gzip_source(url: str, local_path: Path | None):
    if local_path and local_path.exists() and local_path.stat().st_size > 0:
        return gzip.open(local_path, "rt", encoding="utf-8")
    request = Request(url, headers={"User-Agent": "InfTechs-academic-pipeline/1.0"})
    raw = urlopen(request, timeout=120)
    return io.TextIOWrapper(gzip.GzipFile(fileobj=raw), encoding="utf-8")


def iter_jsonl(source, rejections: list[dict], file_name: str, max_lines: int | None):
    for line_no, line in enumerate(source, 1):
        if max_lines and line_no > max_lines:
            break
        try:
            yield line_no, json.loads(line)
        except json.JSONDecodeError:
            rejections.append({"file": file_name, "line": line_no, "reason": "invalid_json"})
            continue


def generate_sample(processed: Path, n_products: int, n_reviews: int) -> dict:
    rng = random.Random(2023)
    products = []
    for i in range(n_products):
        family = FAMILIES[i % len(FAMILIES)]
        title = rng.choice(SAMPLE_TITLES[family])
        parent = f"B0{i:08d}"
        missing_price = rng.random() < 0.18
        products.append({
            "parent_asin": parent,
            "title": f"{title} model {i}",
            "average_rating": round(rng.uniform(3.2, 4.9), 2),
            "rating_number": rng.randint(5, 2400),
            "features": [f"{family} component", "desktop pc part"],
            "description": [f"Replacement {family} for desktop computers."],
            "price": None if missing_price else round(rng.lognormvariate(4.2, 0.7), 2),
            "store": rng.choice(["Amazon.com", "Newegg", None, "Corsair", "ASUS"]),
            "categories": ["Electronics", "Computers", family],
            "details": {"Brand": rng.choice(["AMD", "Intel", "ASUS", "Corsair", "Samsung", None, "Logitech"])},
            "main_category": "Electronics",
            "component_family": family,
        })
    write_jsonl(processed / "products.jsonl", products)

    reviews = []
    start = int(datetime_to_unix(2016, 1, 1))
    end = int(datetime_to_unix(2023, 9, 1))
    snippets = [
        "Installed in a desktop build without issues.",
        "Cable management was annoying but the part is fine.",
        "Runs warmer than I expected in summer.",
        "Packaging arrived dented, product itself looks new.",
        "Firmware update needed before first use.",
        "Noise is acceptable at stock clocks.",
        "Would buy again for a second machine.",
        "Support did not answer my ticket.",
        "Fits the case, screws were missing.",
        "Benchmark numbers match the listing.",
    ]
    weights = [0.07, 0.08, 0.10, 0.22, 0.53]
    for j in range(n_reviews):
        product = products[rng.randrange(len(products))]
        rating = rng.choices([1, 2, 3, 4, 5], weights=weights)[0]
        ts = rng.randint(start, end)
        extra = rng.choice(snippets)
        if rating >= 4:
            text = f"{extra} Mostly satisfied with this {product['component_family']}."
        elif rating == 3:
            text = f"{extra} Mixed feelings about this {product['component_family']}."
        else:
            text = f"{extra} Disappointed with this {product['component_family']} after a few days."
        if rng.random() < 0.12:
            text = extra
        reviews.append({
            "rating": rating,
            "title": rng.choice(["Ok", "Notes", "Build log", "After two weeks"]),
            "text": text,
            "asin": product["parent_asin"] + "V",
            "parent_asin": product["parent_asin"],
            "user_id": f"U{rng.randint(1, n_reviews // 2)}",
            "timestamp": ts * 1000 if rng.random() < 0.2 else ts,
            "verified_purchase": rng.random() < 0.72,
            "helpful_votes": rng.randint(0, 40) if rng.random() < 0.3 else 0,
            "component_family": product["component_family"],
        })
    write_jsonl(processed / "reviews.jsonl", reviews)
    return {
        "products_selected": len(products),
        "reviews_selected": len(reviews),
        "source_mode": "sample",
    }


def datetime_to_unix(year: int, month: int, day: int) -> int:
    from datetime import datetime, timezone
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


def collect_products(source, rejections, max_lines, max_products, fraction) -> tuple[dict, dict]:
    selected = {}
    selection_heap = []
    stats = {"meta_lines": 0, "unmatched": 0, "invalid_parent": 0, "review_required": 0}
    for line_no, item in iter_jsonl(source, rejections, "meta_Electronics.jsonl.gz", max_lines):
        stats["meta_lines"] = line_no
        parent = item.get("parent_asin")
        if not parent:
            stats["invalid_parent"] += 1
            rejections.append({"file": "meta_Electronics.jsonl.gz", "line": line_no, "reason": "missing_parent_asin"})
            continue
        family = classify(item)
        if not family:
            stats["unmatched"] += 1
            stats["review_required"] += 1
            if stats["review_required"] <= 400:
                rejections.append({
                    "file": "meta_Electronics.jsonl.gz",
                    "line": line_no,
                    "reason": "review_required",
                    "title": str(item.get("title") or "")[:180],
                })
            continue
        parent = str(parent)
        if parent in selected:
            continue
        score = stable_hash_score(parent)
        if score / 16**16 >= fraction:
            continue
        record = {**item, "component_family": family}
        if not max_products:
            selected[parent] = record
        elif len(selected) < max_products:
            selected[parent] = record
            heapq.heappush(selection_heap, (-score, parent))
        elif score < -selection_heap[0][0]:
            _, discarded_parent = heapq.heapreplace(selection_heap, (-score, parent))
            del selected[discarded_parent]
            selected[parent] = record
        if line_no % 50_000 == 0:
            print(f"[metadata] linhas={line_no:,} produtos={len(selected):,} review_required={stats['review_required']:,}", flush=True)
    return selected, stats


def collect_reviews(source, selected, rejections, max_lines, max_reviews, target_bytes, current_bytes):
    review_count = 0
    review_bytes = 0
    written_bytes = current_bytes
    kept = []
    for line_no, review in iter_jsonl(source, rejections, "Electronics.jsonl.gz", max_lines):
        parent = review.get("parent_asin")
        if parent not in selected:
            continue
        review["component_family"] = selected[parent]["component_family"]
        encoded = (json.dumps(review, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        if target_bytes and written_bytes + len(encoded) > target_bytes:
            break
        kept.append(review)
        written_bytes += len(encoded)
        review_count += 1
        review_bytes += len(encoded)
        if max_reviews and review_count >= max_reviews:
            break
        if line_no % 200_000 == 0:
            print(f"[reviews] linhas={line_no:,} selecionadas={review_count:,}", flush=True)
    return kept, review_count, review_bytes, written_bytes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--source", choices=["stream", "files", "sample"], default="stream")
    parser.add_argument("--target-gib", default=0.25, type=float)
    parser.add_argument("--selection-fraction", default=1.0, type=float)
    parser.add_argument("--max-meta-lines", default=250_000, type=int)
    parser.add_argument("--max-review-lines", default=1_500_000, type=int)
    parser.add_argument("--max-products", default=8_000, type=int)
    parser.add_argument("--max-reviews", default=80_000, type=int)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--sample-products", default=900, type=int)
    parser.add_argument("--sample-reviews", default=12_000, type=int)
    args = parser.parse_args()

    raw = args.data_dir / "raw"
    processed = args.data_dir / "processed"
    raw.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    rejections: list[dict] = []
    run_id = uuid.uuid4().hex

    if args.source == "sample":
        sample_stats = generate_sample(processed, args.sample_products, args.sample_reviews)
        report = {
            "run_id": run_id,
            "source": {"mode": "sample", "note": "Corpus sintético para teste do pipeline; não representa Amazon Reviews 2023."},
            "target_gib": args.target_gib,
            **sample_stats,
            "generated_at_unix": int(time.time()),
        }
        (processed / "run_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
        return 0

    meta_path = raw / "meta_Electronics.jsonl.gz"
    review_path = raw / "Electronics.jsonl.gz"
    if args.source == "files":
        if not args.skip_download:
            download(META_URL, meta_path)
            download(REVIEW_URL, review_path)

    products_temp = processed / f"products.{run_id}.tmp"
    reviews_temp = processed / f"reviews.{run_id}.tmp"
    with ExitStack() as stack:
        meta_src = stack.enter_context(open_gzip_source(
            META_URL, meta_path if meta_path.exists() else None
        ))
        review_src = stack.enter_context(open_gzip_source(
            REVIEW_URL, review_path if review_path.exists() else None
        ))
        try:
            selected, meta_stats = collect_products(
                meta_src, rejections, args.max_meta_lines, args.max_products, args.selection_fraction
            )
            print(f"[metadata] produtos selecionados={len(selected):,}", flush=True)
            write_jsonl(products_temp, selected.values())
            meta_bytes = products_temp.stat().st_size

            reviews, review_count, review_bytes, written_bytes = collect_reviews(
                review_src,
                selected,
                rejections,
                args.max_review_lines,
                args.max_reviews,
                int(args.target_gib * 1024**3) if args.target_gib else None,
                meta_bytes,
            )
            write_jsonl(reviews_temp, reviews)
            os.replace(products_temp, processed / "products.jsonl")
            os.replace(reviews_temp, processed / "reviews.jsonl")
        finally:
            products_temp.unlink(missing_ok=True)
            reviews_temp.unlink(missing_ok=True)

    rejection_counts = {}
    for rejection in rejections:
        reason = rejection["reason"]
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
    report = {
            "run_id": run_id,
            "source": {
                "mode": args.source,
                "metadata_url": META_URL,
                "review_url": REVIEW_URL,
                "product_selection": "lowest SHA-256 parent_asin hashes in the inspected metadata prefix",
            },
            "target_gib": args.target_gib,
            "selection_fraction": args.selection_fraction,
            "products_selected": len(selected),
            "reviews_selected": review_count,
            "metadata_bytes": meta_bytes,
            "reviews_bytes": review_bytes,
            "total_processed_bytes": written_bytes,
            "meta_stats": meta_stats,
            "rejections": len(rejections),
            "rejection_log_limit": 400,
            "rejection_log_truncated": meta_stats["review_required"] > 400,
            "rejection_reasons": rejection_counts,
            "generated_at_unix": int(time.time()),
        }
    (processed / "run_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_jsonl(processed / "acquisition_rejections.jsonl", rejections)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
