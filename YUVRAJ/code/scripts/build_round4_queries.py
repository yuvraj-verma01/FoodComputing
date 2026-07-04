"""Build Round 4 MediaCloud query plan.

Round 4 strategy: 6 human-approved new keywords from rescreen corpus analysis.
  - raids          (plural enforcement action)
  - adulterated food (food adulteration context with oil)
  - administration fda (FDA authority angle)
  - unhygienic conditions (manufacturing violations)
  - oils           (plural form: edible oils, cooking oils)
  - fsda           (Food Safety & Drug Administration, state-level)

Same NOT block and India collections as Round 3.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RUN_DATE = "2026-06-25"
RUN_NAME = f"edible_oil_adulteration_round_04_{RUN_DATE}"
RUN_DIR  = ROOT / "data" / "runs" / RUN_NAME
SEED_YAML   = ROOT / "config" / "edible_oil_round4_seed_queries.yaml"
CONFIG_YAML = ROOT / "config" / "config_edible_oils_round4.yaml"
SEED_CSV    = RUN_DIR / "proposed_mediacloud_round4_seed_queries.csv"
PREV_URLS_CSV = RUN_DIR / "mediacloud" / "outputs" / "discovery_previously_reviewed_urls.csv"

DATE_START = "2021-01-01"
DATE_END   = RUN_DATE

INDIA_COLLECTIONS = {
    "India - National": 34412118,
    "India - State & Local": 38379954,
    "Andhra Pradesh": 38379967,
    "Arunachal Pradesh": 38379977,
    "Assam": 38379980,
    "Bihar": 38379982,
    "Chandigarh": 38379984,
    "Chhattisgarh": 38379986,
    "Delhi": 38379959,
    "Goa": 38379989,
    "Gujarat": 38379955,
    "Haryana": 38379971,
    "Karnataka": 38379991,
    "Kerala": 38379957,
    "Madhya Pradesh": 38379963,
    "Maharashtra": 38379973,
    "Manipur": 38379995,
    "Meghalaya": 38379998,
    "Mizoram": 38380002,
    "Nagaland": 38380004,
    "Punjab": 38379975,
    "Rajasthan": 38380009,
    "Sikkim": 38380012,
    "Tamil Nadu": 38379969,
    "Tripura": 38380014,
    "Uttar Pradesh": 38379965,
    "Uttarakhand": 38380016,
    "West Bengal": 38379961,
}

HARD_EXCLUSIONS = [
    "ghee", "vanaspati", "Indonesia", "Joko Widodo", "rupiah",
    "oil exports", "export ban", "futures", "derivatives", "SEBI",
    "stock market", "solvent extractors association", "million tonnes",
    "sports drinks", "biodiesel", "bio-diesel", "soda", "diesel",
    "heroin", "hidden in cooking oil cargo",
]

# ── Round 4 approved keyword groups ──────────────────────────────────────────
FRAUD_TERMS = [
    "adulterat*", "contaminat*", "misbrand*", "substandard", "spurious",
    "fake", "counterfeit", "rancid", "tainted", "unfit", "mislabel*",
    "unsafe oil", "unsafe cooking oil", "unsafe edible oil",
]
ENFORCEMENT_TERMS = [
    "FSSAI", "FDA", "FSDA", "food safety", "food safety officer",
    "raid*", "seiz*", "sample collected", "samples collected",
    "lab test", "quality test", "sample failed", "samples failed",
    "license suspended", "licence suspended", "crackdown",
]
OIL_TERMS = [
    "edible oil", "cooking oil", "mustard oil", "vegetable oil", "palm oil",
    "coconut oil", "groundnut oil", "soybean oil", "sunflower oil",
    "edible oils", "cooking oils",
]

# New phrase queries built from approved keywords
NEW_PHRASE_QUERIES = [
    "FSDA edible oil",
    "FSDA oil seized",
    "FSDA oil adulterated",
    "FSDA oil raid",
    "FSDA cooking oil",
    "adulterated food oil",
    "adulterated food items oil",
    "food safety raids oil",
    "unhygienic oil unit",
    "unhygienic conditions edible oil",
    "edible oils seized",
    "cooking oils adulterated",
    "adulterated oils seized",
]

# Proximity combos
NEW_PROXIMITY = [
    ("proximity_fsda_oil",        "FSDA oil",        5),
    ("proximity_oils_seized",     "oils seized",     5),
    ("proximity_oil_raids",       "oil raids",       5),
    ("proximity_unhygienic_oil",  "unhygienic oil",  8),
    ("proximity_fsda_seized",     "FSDA seized",     8),
    ("proximity_food_raids_oil",  "food raids oil", 10),
]


def scoped_query(base: str) -> str:
    return f"({base}) AND NOT {or_group(HARD_EXCLUSIONS)}"


def or_group(terms: list[str]) -> str:
    return "(" + " OR ".join(format_term(t) for t in terms) + ")"


def or_group_field(terms: list[str], field: str) -> str:
    return "(" + " OR ".join(f"{field}:{format_term(t)}" for t in terms) + ")"


def format_term(term: str) -> str:
    if ":" in term or "*" in term:
        return term
    if " " in term or "-" in term:
        return f'"{term}"'
    return term


def slug(text: str) -> str:
    return text.lower().replace(" ", "_").replace("-", "_")


def build_queries() -> list[dict]:
    rows: list[dict] = []

    # ── Family 1: Phrase queries ──────────────────────────────────────────────
    for phrase in NEW_PHRASE_QUERIES:
        rows.append({
            "query_id":      f"r4_phrase_{slug(phrase)}",
            "query_family":  "phrase",
            "query":         scoped_query(f'"{phrase}" AND language:en'),
            "signal_mode":   "exact_phrase",
            "reason":        f'Round 4 approved keyword phrase: "{phrase}".',
        })

    # ── Family 2: Boolean — FSDA + oil + enforcement ──────────────────────────
    oil_expr  = or_group(OIL_TERMS + ["oils"])
    enf_expr  = or_group(ENFORCEMENT_TERMS)
    fraud_expr = or_group(FRAUD_TERMS)

    rows.append({
        "query_id":     "r4_boolean_fsda_oil_enforcement",
        "query_family": "boolean",
        "query":        scoped_query(
            f'(FSDA OR "food safety department") AND {oil_expr} AND {enf_expr} AND language:en'
        ),
        "signal_mode":  "fsda_oil_enforcement",
        "reason":       "FSDA (state-level authority) + oil + enforcement action.",
    })

    rows.append({
        "query_id":     "r4_boolean_adulterated_food_oil",
        "query_family": "boolean",
        "query":        scoped_query(
            f'"adulterated food" AND {oil_expr} AND India AND language:en'
        ),
        "signal_mode":  "adulterated_food_oil",
        "reason":       "Adulterated food in context of oil enforcement.",
    })

    rows.append({
        "query_id":     "r4_boolean_unhygienic_oil_authority",
        "query_family": "boolean",
        "query":        scoped_query(
            f'"unhygienic" AND {oil_expr} AND (FSSAI OR FDA OR FSDA) AND India AND language:en'
        ),
        "signal_mode":  "unhygienic_oil_authority",
        "reason":       "Unhygienic manufacturing conditions with oil and food authority.",
    })

    rows.append({
        "query_id":     "r4_boolean_oils_plural_fraud",
        "query_family": "boolean",
        "query":        scoped_query(
            f'("edible oils" OR "cooking oils") AND {fraud_expr} AND India AND language:en'
        ),
        "signal_mode":  "oils_plural_fraud",
        "reason":       "Plural oil forms (edible oils / cooking oils) + fraud terms.",
    })

    rows.append({
        "query_id":     "r4_boolean_fda_oil_raids",
        "query_family": "boolean",
        "query":        scoped_query(
            f'("food and drug administration" OR FDA OR FSDA) AND {oil_expr} AND (raid* OR seiz*) AND India AND language:en'
        ),
        "signal_mode":  "fda_oil_raids",
        "reason":       "FDA/FSDA + oil + raid/seizure.",
    })

    # ── Family 3: Title-only queries (highest crawl priority in pipeline) ─────
    title_oil  = or_group_field(OIL_TERMS + ["oils", "FSDA"], "article_title")
    title_enf  = or_group_field(ENFORCEMENT_TERMS + ["raids", "unhygienic"], "article_title")
    title_fraud = or_group_field(FRAUD_TERMS, "article_title")

    rows.append({
        "query_id":     "r4_title_fsda_oil",
        "query_family": "title_only",
        "query":        scoped_query(
            f'article_title:FSDA AND {or_group_field(OIL_TERMS + ["oils"], "article_title")} AND language:en'
        ),
        "signal_mode":  "title_fsda_oil",
        "reason":       "FSDA and oil term both in article title.",
    })

    rows.append({
        "query_id":     "r4_title_oils_fraud",
        "query_family": "title_only",
        "query":        scoped_query(
            f'{or_group_field(["edible oils", "cooking oils", "oils"], "article_title")} AND {title_fraud} AND language:en'
        ),
        "signal_mode":  "title_oils_plural_fraud",
        "reason":       "Plural oil form and fraud term both in title.",
    })

    rows.append({
        "query_id":     "r4_title_oil_raids",
        "query_family": "title_only",
        "query":        scoped_query(
            f'{or_group_field(OIL_TERMS + ["oils"], "article_title")} AND article_title:raids AND language:en'
        ),
        "signal_mode":  "title_oil_raids",
        "reason":       "Oil term and 'raids' both in title.",
    })

    rows.append({
        "query_id":     "r4_title_unhygienic_oil",
        "query_family": "title_only",
        "query":        scoped_query(
            f'{or_group_field(OIL_TERMS + ["oils"], "article_title")} AND article_title:unhygienic AND language:en'
        ),
        "signal_mode":  "title_unhygienic_oil",
        "reason":       "Oil term and 'unhygienic' both in title.",
    })

    # ── Family 4: Proximity queries ───────────────────────────────────────────
    for qid, phrase, dist in NEW_PROXIMITY:
        rows.append({
            "query_id":     f"r4_{qid}",
            "query_family": "proximity",
            "query":        scoped_query(f'"{phrase}"~{dist} AND language:en'),
            "signal_mode":  f"within_{dist}_words",
            "reason":       f'Terms "{phrase}" within {dist} words.',
        })

    for i, row in enumerate(rows, 1):
        row["query_number"]    = str(i)
        row["date_start"]      = DATE_START
        row["date_end"]        = DATE_END
        row["collection_count"] = str(len(INDIA_COLLECTIONS))
        row["hard_exclusion"]  = "; ".join(HARD_EXCLUSIONS)
        row["breadth"]         = "round4_approved_keywords"

    return rows


def write_previously_reviewed_urls() -> int:
    """Collect all previously seen URLs from all rounds and save for dedup."""
    urls: set[str] = set()
    master = ROOT / "reports/master_corpus/master_all_articles.csv"
    if master.exists():
        for r in csv.DictReader(master.open(encoding="utf-8-sig")):
            if r.get("url"):
                urls.add(r["url"].strip())

    for p in (ROOT / "data/runs").rglob("discovery_url_review.csv"):
        for r in csv.DictReader(p.open(encoding="utf-8-sig")):
            if r.get("url"):
                urls.add(r["url"].strip())

    for p in (ROOT / "data/runs").rglob("metadata_all_articles_review.csv"):
        for r in csv.DictReader(p.open(encoding="utf-8-sig")):
            if r.get("url"):
                urls.add(r["url"].strip())

    rescreen = ROOT / "reports/rescreen/rescreen_all_dropped.csv"
    if rescreen.exists():
        for r in csv.DictReader(rescreen.open(encoding="utf-8-sig")):
            if r.get("url"):
                urls.add(r["url"].strip())

    PREV_URLS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PREV_URLS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["url"])
        w.writeheader()
        for url in sorted(urls):
            w.writerow({"url": url})

    print(f"Previously reviewed URLs saved: {len(urls)} -> {PREV_URLS_CSV}")
    return len(urls)


def write_seed_yaml(rows: list[dict]) -> None:
    payload = {
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "round":         4,
        "strategy":      "6 human-approved keywords from rescreen analysis",
        "approved_keywords": ["raids", "adulterated food", "administration fda",
                              "unhygienic conditions", "oils", "fsda"],
        "seed_keywords": [r["query"] for r in rows],
        "query_rows":    rows,
        "hard_exclusions": HARD_EXCLUSIONS,
        "india_collections": INDIA_COLLECTIONS,
    }
    SEED_YAML.parent.mkdir(parents=True, exist_ok=True)
    SEED_YAML.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def write_seed_csv(rows: list[dict]) -> None:
    SEED_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["query_number", "query_id", "query_family", "query",
                  "signal_mode", "reason", "date_start", "date_end",
                  "collection_count", "hard_exclusion", "breadth"]
    with SEED_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def write_config_yaml() -> None:
    run_rel    = f"data/runs/{RUN_NAME}/mediacloud"
    output_rel = f"{run_rel}/outputs"
    config = {
        "date_range": {"start": DATE_START, "end": DATE_END},
        "discovery": {
            "enabled_sources": ["mediacloud"],
            "mediacloud": {
                "collection_ids":  list(INDIA_COLLECTIONS.values()),
                "max_results":     1000,
                "delay_seconds":   1.5,
                "previously_reviewed_urls_csv": str(PREV_URLS_CSV),
            },
        },
        "crawl": {
            "delay_seconds":      3.0,
            "max_retries":        3,
            "backoff_factor":     2.0,
            "timeout_seconds":    30,
            "user_agent":         "FoodSafetyResearchBot/1.0 (Academic research on Indian edible oil food safety)",
            "respect_robots_txt": True,
            "use_playwright":     False,
        },
        "paths": {
            "raw_html":        f"{run_rel}/raw_html",
            "cleaned_text":    f"{run_rel}/cleaned_text",
            "outputs":         output_rel,
            "db":              f"{output_rel}/articles.db",
            "discovered_urls": f"{output_rel}/discovered_urls.jsonl",
            "articles_jsonl":  f"{output_rel}/articles.jsonl",
            "articles_csv":    f"{output_rel}/articles.csv",
            "report":          f"{output_rel}/report.json",
        },
    }
    CONFIG_YAML.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def print_plan(rows: list[dict]) -> None:
    print("\n" + "=" * 100)
    print(f"ROUND 4 QUERY PLAN — {len(rows)} queries")
    print("=" * 100)
    fam = None
    for row in rows:
        if row["query_family"] != fam:
            fam = row["query_family"]
            print(f"\n----- FAMILY: {fam.upper()} -----")
        print(f"\n[{row['query_number']}] {row['query_id']}  ({row['signal_mode']})")
        print(f"    reason: {row['reason']}")
        print(f"    QUERY:  {row['query']}")
    from collections import Counter
    fam_counts = Counter(r["query_family"] for r in rows)
    print("\n" + "=" * 100)
    print(f"Families: {dict(fam_counts)}")
    print(f"Date range: {DATE_START} to {DATE_END}")
    print(f"Collections: {len(INDIA_COLLECTIONS)} India (National + 27 State/Local)")
    print(f"NOT block: {len(HARD_EXCLUSIONS)} terms")
    print("=" * 100)


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_queries()
    n_prev = write_previously_reviewed_urls()
    write_seed_yaml(rows)
    write_seed_csv(rows)
    write_config_yaml()
    print_plan(rows)
    print(json.dumps({
        "queries":             len(rows),
        "previously_seen_urls": n_prev,
        "run_dir":             str(RUN_DIR),
        "config_yaml":         str(CONFIG_YAML),
        "seed_csv":            str(SEED_CSV),
        "NOTE":                "Plan only. Run the pipeline next.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
