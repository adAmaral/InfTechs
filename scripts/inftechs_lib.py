"""Funções compartilhadas do pipeline InfTechs."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

KEYWORDS = {
    "gpu": [
        r"\bgraphics card\b", r"\bvideo card\b", r"\bgpu\b",
        r"\bgraphics board\b", r"\bgeforce\s+(?:rtx|gtx)\b", r"\bradeon\s+rx\b",
    ],
    "cpu": [
        r"\bcpu\b", r"\bprocessor\b", r"\bthreadripper\b", r"\bxeon\b",
        r"\bryzen\b",
    ],
    "ram": [
        r"\bmemory\s+ram\b", r"\bdesktop memory\b", r"\bddr[3-5]\b",
        r"\bsodimm\b", r"\bdimm\b",
    ],
    "motherboard": [r"\bmotherboards?\b", r"\bmainboards?\b"],
    "storage": [
        r"\bsolid state drive\b", r"\bssd\b", r"\bhard drive\b", r"\bhdd\b",
        r"\bnvme\b", r"\bm\.2\b",
    ],
    "case": [
        r"\bpc case\b", r"\bcomputer case\b", r"\btower case\b",
        r"\bcomputer chassis\b", r"\bpc chassis\b",
    ],
    "power_supply": [
        r"\b(?:atx|modular|desktop|pc)\s+power supply\b",
        r"\bpower supply unit\b", r"\bpsu\b", r"\b80\s*plus\b",
    ],
    "cooling": [
        r"\bcpu coolers?\b", r"\bcpu cooling\b", r"\bliquid cooler\b", r"\bwater cooling\b",
        r"\bheatsink\b", r"\bpc fan\b", r"\bcomputer case fan\b",
        r"\bgpu cooler\b", r"\bgpu water block\b", r"\bwater block\b",
        r"\bcooling fan\b", r"\bfan assembly\b",
    ],
    "peripherals": [
        r"\bcomputer keyboard\b", r"\bgaming keyboard\b", r"\bkeyboard\b",
        r"\bcomputer mouse\b", r"\bgaming mouse\b", r"\bwebcam\b",
        r"\bcomputer monitor\b", r"\bmonitor\b", r"\bcomputer speaker\b",
    ],
}
CATEGORY_FAMILIES = {
    "cpu processors": "cpu",
    "cpus": "cpu",
    "graphics cards": "gpu",
    "motherboards": "motherboard",
    "memory": "ram",
    "desktop memory": "ram",
    "laptop memory": "ram",
    "external hard drives": "storage",
    "internal hard drives": "storage",
    "external solid state drives": "storage",
    "internal solid state drives": "storage",
    "internal power supplies": "power_supply",
    "computer cases": "case",
    "cpu cooling fans": "cooling",
    "case fans": "cooling",
    "water cooling systems": "cooling",
    "heatsinks": "cooling",
    "graphics card fans": "cooling",
    "monitors": "peripherals",
    "keyboards": "peripherals",
    "keyboard & mouse combos": "peripherals",
    "mice": "peripherals",
    "webcams": "peripherals",
}
COOLING_PATTERNS = KEYWORDS["cooling"]

POSITIVE_TERMS = {
    "excellent", "great", "good", "love", "perfect", "fast", "quiet", "solid",
    "recommend", "works", "amazing", "stable", "reliable", "value", "smooth",
}
NEGATIVE_TERMS = {
    "bad", "poor", "terrible", "broken", "slow", "hot", "noisy", "fail",
    "failed", "return", "waste", "defect", "dead", "crash", "overheat", "cheap",
}


def flatten(value) -> str:
    if isinstance(value, dict):
        return " ".join(f"{k} {flatten(v)}" for k, v in value.items())
    if isinstance(value, list):
        return " ".join(flatten(v) for v in value)
    return str(value or "")


def clean_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def classify(item: dict) -> str | None:
    title = clean_text(item.get("title")).lower()
    categories = item.get("categories")
    category_leaf = (
        clean_text(categories[-1]).lower()
        if isinstance(categories, list) and categories
        else ""
    )
    full_system = re.search(
        r"\b(?:laptop|notebook|chromebook|tablet|gaming pc|desktop computer|desktop pc|"
        r"gaming machine|computer system|pc system|workstation|server|all-in-one pc|"
        r"prodesk|thinkcentre|optiplex|alienware aurora)\b",
        title,
    )
    component_accessory = re.search(
        r"\b(?:replacement|upgrade|compatible|memory for|ssd for|for laptops?|for notebooks?)\b",
        title,
    )
    if full_system and not component_accessory:
        return None
    if re.search(
        r"\b(?:sleeve|pouch|carrying bag|dust cover|case cover|screw kit|"
        r"adapter|charger|power cord|power supply cord|extension cable|screws?|"
        r"security system|camcorder|television|smart tv|radio|car roof|"
        r"car heater|vehicle|rear.?view|doorphone|doorbell|ipod|iphone|ipad|"
        r"webcam backdrop|thermal paste|refurbished|cpu holder|cpu mount|cpu bracket)\b",
        title,
    ):
        return None
    if re.search(
        r"\b(?:keyboard cover|keyboard skin|keyboard case|hard shell case|"
        r"laptop case|macbook case|sound card)\b",
        title,
    ):
        return None
    category_family = CATEGORY_FAMILIES.get(category_leaf)
    if category_family:
        return category_family
    if category_leaf in {
        "bags, cases & sleeves",
        "hard shell cases",
        "hard drive bags & cases",
        "keyboard cases",
        "keyboard skins",
        "internal sound cards",
        "monitor arms",
        "monitor stands",
        "screen protectors",
        "skins & decals",
    }:
        return None
    has_cooling_signal = any(re.search(pattern, title) for pattern in COOLING_PATTERNS)
    has_graphics_card_signal = any(
        re.search(pattern, title)
        for pattern in (KEYWORDS["gpu"][0], KEYWORDS["gpu"][1], KEYWORDS["gpu"][3])
    )
    if has_cooling_signal and not has_graphics_card_signal:
        return "cooling"
    if re.search(r"\b(?:motherboards?|mainboards?)\b", title) and not re.search(
        r"\b(?:ram kit|memory module|desktop memory|sodimm|dimm)\b", title
    ):
        return "motherboard"
    for family, patterns in KEYWORDS.items():
        if any(re.search(pattern, title) for pattern in patterns):
            return family
    return None


def safe_year(timestamp):
    try:
        return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).year
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def safe_timestamp(timestamp):
    try:
        return datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def sentiment_score(text: str) -> float:
    tokens = re.findall(r"[a-z]+", (text or "").lower())
    if not tokens:
        return 0.0
    pos = sum(1 for token in tokens if token in POSITIVE_TERMS)
    neg = sum(1 for token in tokens if token in NEGATIVE_TERMS)
    return (pos - neg) / math.sqrt(len(tokens))


def inventory(records: list[dict], name: str) -> dict:
    fields = Counter()
    for record in records:
        fields.update(record.keys())
    n = max(len(records), 1)
    return {
        "dataset": name,
        "records": len(records),
        "fields": [
            {"name": field, "records_present": count, "coverage_pct": round(count / n * 100, 2)}
            for field, count in sorted(fields.items())
        ],
    }


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def write_jsonl(path: Path, records) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count
