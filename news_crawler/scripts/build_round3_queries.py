"""Build the Round 3 Media Cloud query plan.

Round 3 strategy = TIGHT. We do NOT re-run the full Round 1+2 query bank
(that would just re-discover already-reviewed URLs). Instead we turn the 17
human-approved NEW keywords into focused queries, and apply the EXPANDED
NOT block (old hard exclusions + 6 new human-approved NOT terms) to every query.

This script only writes the query plan (CSV + YAML + config). It does NOT
contact Media Cloud. Run run_combined_mediacloud_discovery.py separately to send.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RUN_NAME = "edible_oil_adulteration_round_03_2026-06-23"
RUN_DIR = ROOT / "data" / "runs" / RUN_NAME
SEED_YAML = ROOT / "config" / "edible_oil_round3_seed_queries.yaml"
CONFIG_YAML = ROOT / "config" / "config_edible_oils_round3.yaml"
SEED_CSV = RUN_DIR / "proposed_mediacloud_round3_seed_queries.csv"

DATE_START = "2021-01-01"
DATE_END = "2026-06-23"

# Same 28 India collections as Round 2
INDIA_COLLECTIONS = {
    "India - National": 34412118,
    "India - State & Local": 38379954,
    "Andhra Pradesh, India - State & Local": 38379967,
    "Arunachal Pradesh, India - State & Local": 38379977,
    "Assam, India - State & Local": 38379980,
    "Bihar, India - State & Local": 38379982,
    "Chandigarh, India - State & Local": 38379984,
    "Chhattisgarh, India - State & Local": 38379986,
    "Delhi, India - State & Local": 38379959,
    "Goa, India - State & Local": 38379989,
    "Gujarat, India - State & Local": 38379955,
    "Haryana, India - State & Local": 38379971,
    "Karnataka, India - State & Local": 38379991,
    "Kerala, India - State & Local": 38379957,
    "Madhya Pradesh, India - State & Local": 38379963,
    "Maharashtra, India - State & Local": 38379973,
    "Manipur, India - State & Local": 38379995,
    "Meghalaya, India - State & Local": 38379998,
    "Mizoram, India - State & Local": 38380002,
    "Nagaland, India - State & Local": 38380004,
    "Punjab, India - State & Local": 38379975,
    "Rajasthan, India - State & Local": 38380009,
    "Sikkim, India - State & Local": 38380012,
    "Tamil Nadu, India - State & Local": 38379969,
    "Tripura, India - State & Local": 38380014,
    "Uttar Pradesh, India - State & Local": 38379965,
    "Uttarakhand, India - State & Local": 38380016,
    "West Bengal, India - State & Local": 38379961,
}

# ── Expanded NOT block: Round 1/2 exclusions + 6 new human-approved NOT terms ──
OLD_HARD_EXCLUSIONS = [
    "ghee", "vanaspati", "Indonesia", "Joko Widodo", "rupiah",
    "rupiah per litre", "oil exports", "export ban", "futures", "derivative",
    "derivatives", "SEBI", "stock market", "domestic market",
    "solvent extractors association", "million tonnes", "million tonne",
    "sports drinks", "reused cooking oil", "biodiesel", "bio-diesel",
    "soda", "diesel", "heroin", "hidden in cooking oil cargo",
]
# The 6 human-approved NOT terms (paneer/dairy products/soybean corn) are applied
# at the RELEVANCE-SCORER level (NON_OIL_FOOD_TERMS), NOT here as query exclusions,
# so multi-item raids that mention oil AND paneer are still fetched and reviewed.
HARD_EXCLUSIONS = OLD_HARD_EXCLUSIONS

# ── Fraud / enforcement signal groups (re-used) ────────────────────────────────
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

# ── The 17 human-approved Round 3 keywords, grouped by how they query best ─────

# Strong exact-phrase queries (inherently about oil being adulterated)
NEW_PHRASE_QUERIES = [
    "tainted edible oil",
    "unfit edible oil",
    "mislabelled oils",
    "substandard edible oil",
    "collected edible oil samples",
    "edible oil samples",
    "seized adulterated food items",
    "adulterated food items",
    "edible oil traders",
    "fake oil",
]

# New oil-product variants -> combine with fraud/enforcement in a Boolean query
NEW_PRODUCT_VARIANTS = [
    "palm olein oil",
    "palmolein oil",
    "refined soybean oil",
    "edible oils",
]

# New proximity combos (loose word adjacency)
NEW_PROXIMITY = [
    ("proximity_edible_oil_tainted", "edible oil tainted", 8),
    ("proximity_edible_oil_unfit", "edible oil unfit", 8),
    ("proximity_edible_oil_substandard", "edible oil substandard", 10),
    ("proximity_oil_samples_failed", "oil samples failed", 8),
    ("proximity_oil_found_substandard", "oil found substandard", 10),
]

# 'food and drug administration' + 'oil samples' join the enforcement-combo query


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_queries()
    write_seed_yaml(rows)
    write_seed_csv(rows)
    write_config_yaml()
    print_queries(rows)
    print(json.dumps({
        "queries": len(rows),
        "run_dir": str(RUN_DIR),
        "seed_yaml": str(SEED_YAML),
        "seed_csv": str(SEED_CSV),
        "config_yaml": str(CONFIG_YAML),
        "NOTE": "Plan only. No Media Cloud request was sent.",
    }, indent=2))
    return 0


def build_queries() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    # Family 1 — exact phrase queries for new strong phrases
    for phrase in NEW_PHRASE_QUERIES:
        rows.append({
            "query_id": f"r3_phrase_{slug(phrase)}",
            "query_family": "phrase",
            "query": scoped_query(f'"{phrase}" AND language:en'),
            "product_groups": "new_phrase",
            "signal_mode": "exact_phrase",
            "reason": f'Round 3 new keyword exact phrase: "{phrase}".',
        })

    # Family 2 — new oil-product variants AND fraud terms
    product_expr = or_group(NEW_PRODUCT_VARIANTS)
    fraud_expr = or_group(FRAUD_TERMS)
    rows.append({
        "query_id": "r3_boolean_new_oil_variants_fraud",
        "query_family": "boolean",
        "query": scoped_query(f"{product_expr} AND {fraud_expr} AND language:en"),
        "product_groups": "new_oil_variants",
        "signal_mode": "fraud_only",
        "reason": "New oil-product variants co-occur with adulteration/fraud terms.",
    })

    # Family 3 — new oil-product variants AND enforcement terms
    enf_expr = or_group(ENFORCEMENT_TERMS)
    rows.append({
        "query_id": "r3_boolean_new_oil_variants_enforcement",
        "query_family": "boolean",
        "query": scoped_query(f"{product_expr} AND {enf_expr} AND language:en"),
        "product_groups": "new_oil_variants",
        "signal_mode": "enforcement_only",
        "reason": "New oil-product variants co-occur with enforcement/evidence terms.",
    })

    # Family 4 — generic new terms (oil samples / traders / FDA) AND enforcement
    generic_terms = ["oil samples", "edible oil traders", "food and drug administration"]
    generic_expr = or_group(generic_terms)
    rows.append({
        "query_id": "r3_boolean_generic_new_terms_enforcement",
        "query_family": "boolean",
        "query": scoped_query(f"{generic_expr} AND {enf_expr} AND {or_group(['oil'])} AND language:en"),
        "product_groups": "generic_new_terms",
        "signal_mode": "enforcement_plus_oil",
        "reason": "Generic new terms gated by enforcement language AND an oil mention.",
    })

    # Family 5 — title-only queries (high precision: terms must be in the headline)
    title_product_expr = or_group_field(NEW_PRODUCT_VARIANTS + ["edible oil", "cooking oil", "mustard oil"], "article_title")
    title_fraud_expr = or_group_field(FRAUD_TERMS, "article_title")
    title_enf_expr = or_group_field(ENFORCEMENT_TERMS, "article_title")
    rows.append({
        "query_id": "r3_title_oils_fraud",
        "query_family": "title_only",
        "query": scoped_query(f"{title_product_expr} AND {title_fraud_expr} AND language:en"),
        "product_groups": "new_variants+core_oils",
        "signal_mode": "title_fraud",
        "reason": "Oil term and a fraud term both appear in the article title.",
    })
    rows.append({
        "query_id": "r3_title_oils_enforcement",
        "query_family": "title_only",
        "query": scoped_query(f"{title_product_expr} AND {title_enf_expr} AND language:en"),
        "product_groups": "new_variants+core_oils",
        "signal_mode": "title_enforcement",
        "reason": "Oil term and an enforcement term both appear in the article title.",
    })

    # Family 6 — proximity queries
    for query_id, phrase, dist in NEW_PROXIMITY:
        rows.append({
            "query_id": f"r3_{query_id}",
            "query_family": "proximity",
            "query": scoped_query(f'"{phrase}"~{dist} AND language:en'),
            "product_groups": "phrase_proximity",
            "signal_mode": f"within_{dist}_words",
            "reason": f'Find stories where "{phrase}" terms appear within {dist} words.',
        })

    for i, row in enumerate(rows, start=1):
        row["query_number"] = str(i)
        row["date_start"] = DATE_START
        row["date_end"] = DATE_END
        row["collection_count"] = str(len(INDIA_COLLECTIONS))
        row["hard_exclusion"] = "; ".join(HARD_EXCLUSIONS)
        row["breadth"] = "round3_tight_new_keywords_only"
    return rows


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


def print_queries(rows: list[dict[str, str]]) -> None:
    print("\n" + "=" * 100)
    print(f"ROUND 3 QUERY PLAN — {len(rows)} queries (NOT yet sent)")
    print("=" * 100)
    fam = None
    for row in rows:
        if row["query_family"] != fam:
            fam = row["query_family"]
            print(f"\n----- FAMILY: {fam.upper()} -----")
        print(f"\n[{row['query_number']}] {row['query_id']}  ({row['signal_mode']})")
        print(f"    reason: {row['reason']}")
        print(f"    QUERY:  {row['query']}")
    print("\n" + "=" * 100)
    print(f"Date range: {DATE_START} to {DATE_END}")
    print(f"Collections: {len(INDIA_COLLECTIONS)} India (National + 27 State/Local)")
    print(f"NOT block ({len(HARD_EXCLUSIONS)} terms): {', '.join(HARD_EXCLUSIONS)}")
    print("=" * 100)


def write_seed_yaml(rows: list[dict[str, str]]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round": 3,
        "strategy": "tight: only the 17 human-approved new keywords; expanded NOT block.",
        "seed_keywords": [r["query"] for r in rows],
        "query_rows": rows,
        "new_phrase_queries": NEW_PHRASE_QUERIES,
        "new_product_variants": NEW_PRODUCT_VARIANTS,
        "new_proximity": [{"id": p[0], "phrase": p[1], "distance": p[2]} for p in NEW_PROXIMITY],
        "hard_exclusions": HARD_EXCLUSIONS,
        "india_collections": INDIA_COLLECTIONS,
    }
    SEED_YAML.parent.mkdir(parents=True, exist_ok=True)
    SEED_YAML.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_seed_csv(rows: list[dict[str, str]]) -> None:
    SEED_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "query_number", "query_id", "query_family", "query", "product_groups",
        "signal_mode", "reason", "date_start", "date_end", "collection_count",
        "hard_exclusion", "breadth",
    ]
    with SEED_CSV.open("w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def write_config_yaml() -> None:
    run_rel = f"data/runs/{RUN_NAME}/mediacloud"
    output_rel = f"{run_rel}/outputs"
    config = {
        "date_range": {"start": DATE_START, "end": DATE_END},
        "discovery": {
            "enabled_sources": ["mediacloud"],
            "mediacloud": {
                "collection_ids": list(INDIA_COLLECTIONS.values()),
                "max_results": 1000,
                "delay_seconds": 1.5,
            },
        },
        "crawl": {
            "delay_seconds": 3.0,
            "max_retries": 3,
            "backoff_factor": 2.0,
            "timeout_seconds": 30,
            "user_agent": (
                "FoodSafetyResearchBot/1.0 "
                "(Academic research on Indian edible oil food safety)"
            ),
            "respect_robots_txt": True,
            "use_playwright": False,
        },
        "paths": {
            "raw_html": f"{run_rel}/raw_html",
            "cleaned_text": f"{run_rel}/cleaned_text",
            "outputs": output_rel,
            "db": f"{output_rel}/articles.db",
            "discovered_urls": f"{output_rel}/discovered_urls.jsonl",
            "articles_jsonl": f"{output_rel}/articles.jsonl",
            "articles_csv": f"{output_rel}/articles.csv",
            "report": f"{output_rel}/report.json",
        },
    }
    CONFIG_YAML.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_YAML.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=False), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
