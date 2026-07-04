"""Build one combined Media Cloud query plan for edible-oil discovery.

This run keeps the original Boolean idea, but adds title-only Boolean queries
and proximity queries in the same run. Edit the dictionaries below to change
terms or query families.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
RUN_NAME = "edible_oil_adulteration_round_02_2026-06-23"
RUN_DIR = ROOT / "data" / "runs" / RUN_NAME
SEED_YAML = ROOT / "config" / "edible_oil_combined_seed_queries.yaml"
CONFIG_YAML = ROOT / "config" / "config_edible_oils_combined.yaml"
SEED_CSV = RUN_DIR / "proposed_mediacloud_combined_seed_queries.csv"

DATE_START = "2021-01-01"
DATE_END = "2026-06-23"


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


QUERY_GROUPS = {
    "core_oils": [
        "edible oil",
        "cooking oil",
        "vegetable oil",
        "refined oil",
        "loose oil",
        "loose edible oil",
    ],
    "named_oils": [
        "mustard oil",
        "palm oil",
        "soybean oil",
        "sunflower oil",
        "groundnut oil",
        "coconut oil",
        "rice bran oil",
        "cottonseed oil",
        "sesame oil",
        "olive oil",
        "rapeseed-mustard oil",
    ],
    "fraud_terms": [
        "adulterat*",
        "contaminat*",
        "misbrand*",
        "substandard",
        "spurious",
        "fake",
        "counterfeit",
        "rancid",
        "reused oil",
        "recycled oil",
        "unsafe oil",
        "unsafe cooking oil",
        "unsafe edible oil",
        "mixed with",
    ],
    "enforcement_org_terms": [
        "FSSAI",
        "FDA",
        "FSDA",
        "food safety",
        "food safety department",
        "food safety officer",
    ],
    "enforcement_action_terms": [
        "raid*",
        "seiz*",
        "sample collected",
        "samples collected",
        "samples sent",
        "lab test",
        "quality test",
        "prosecut*",
        "penal*",
        "fine",
        "ban*",
        "license suspended",
        "licence suspended",
        "shop sealed",
        "warehouse",
        "godown",
        "arrest*",
        "crackdown",
        "inspection",
    ],
    "hard_exclusions": [
        "ghee",
        "vanaspati",
        "Indonesia",
        "Joko Widodo",
        "rupiah",
        "rupiah per litre",
        "oil exports",
        "export ban",
        "futures",
        "derivative",
        "derivatives",
        "SEBI",
        "stock market",
        "domestic market",
        "solvent extractors association",
        "million tonnes",
        "million tonne",
        "sports drinks",
        "reused cooking oil",
        "biodiesel",
        "bio-diesel",
        "soda",
        "diesel",
        "heroin",
        "hidden in cooking oil cargo",
    ],
}


BOOLEAN_TEMPLATES = [
    {
        "query_id": "boolean_core_oils_fraud",
        "product_groups": ["core_oils"],
        "signal_mode": "fraud_only",
        "reason": "Core edible/cooking oil phrases co-occur with direct adulteration/fraud terms.",
    },
    {
        "query_id": "boolean_named_oils_fraud",
        "product_groups": ["named_oils"],
        "signal_mode": "fraud_only",
        "reason": "Specific oil types co-occur with direct adulteration/fraud terms.",
    },
    {
        "query_id": "boolean_oils_enforcement_evidence",
        "product_groups": ["core_oils", "named_oils"],
        "signal_mode": "fraud_and_enforcement",
        "reason": "Oil terms plus both adulteration/fraud and enforcement/evidence language.",
    },
    {
        "query_id": "boolean_oils_enforcement_only",
        "product_groups": ["core_oils", "named_oils"],
        "signal_mode": "enforcement_only",
        "reason": "Oil terms plus enforcement/evidence language, for raid/seizure/lab-test articles that do not explicitly say adulteration.",
    },
]


TITLE_TEMPLATES = [
    {
        "query_id": "title_core_oils_fraud",
        "product_groups": ["core_oils"],
        "signal_groups": ["fraud_terms"],
        "reason": "Core oil term and fraud term both appear in the article title.",
    },
    {
        "query_id": "title_named_oils_fraud",
        "product_groups": ["named_oils"],
        "signal_groups": ["fraud_terms"],
        "reason": "Named oil term and fraud term both appear in the article title.",
    },
    {
        "query_id": "title_oils_enforcement",
        "product_groups": ["core_oils", "named_oils"],
        "signal_groups": ["enforcement_org_terms", "enforcement_action_terms"],
        "reason": "Oil term and enforcement/evidence term both appear in the article title.",
    },
]


PROXIMITY_TEMPLATES = [
    ("proximity_edible_oil_adulteration", "edible oil adulteration", 10),
    ("proximity_edible_oil_adulterated", "edible oil adulterated", 10),
    ("proximity_edible_oil_seized", "edible oil seized", 10),
    ("proximity_edible_oil_food_safety", "edible oil food safety", 10),
    ("proximity_cooking_oil_adulterated", "cooking oil adulterated", 10),
    ("proximity_cooking_oil_fake", "cooking oil fake", 8),
    ("proximity_mustard_oil_adulteration", "mustard oil adulteration", 10),
    ("proximity_mustard_oil_adulterated", "mustard oil adulterated", 10),
    ("proximity_mustard_oil_fake", "mustard oil fake", 8),
    ("proximity_mustard_oil_seized", "mustard oil seized", 10),
    ("proximity_palm_oil_adulteration", "palm oil adulteration", 10),
    ("proximity_coconut_oil_adulteration", "coconut oil adulteration", 10),
    ("proximity_groundnut_oil_adulteration", "groundnut oil adulteration", 10),
    ("proximity_oil_adulteration", "oil adulteration", 6),
    ("proximity_oil_spurious", "oil spurious", 8),
    ("proximity_oil_seized", "oil seized", 8),
    ("proximity_oil_sample_failed", "oil sample failed", 10),
    ("proximity_oil_food_safety", "oil food safety", 10),
]


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_queries()
    write_seed_yaml(rows)
    write_seed_csv(rows)
    write_config_yaml()
    print(
        json.dumps(
            {
                "queries": len(rows),
                "run_dir": str(RUN_DIR),
                "seed_yaml": str(SEED_YAML),
                "seed_csv": str(SEED_CSV),
                "config_yaml": str(CONFIG_YAML),
            },
            indent=2,
        )
    )
    return 0


def build_queries() -> list[dict[str, str]]:
    rows = []
    rows.extend(build_boolean_rows())
    rows.extend(build_title_rows())
    rows.extend(build_proximity_rows())
    for index, row in enumerate(rows, start=1):
        row["query_number"] = str(index)
        row["date_start"] = DATE_START
        row["date_end"] = DATE_END
        row["collection_count"] = str(len(INDIA_COLLECTIONS))
        row["hard_exclusion"] = "; ".join(QUERY_GROUPS["hard_exclusions"])
        row["breadth"] = "combined_boolean_title_proximity"
    return rows


def build_boolean_rows() -> list[dict[str, str]]:
    rows = []
    for template in BOOLEAN_TEMPLATES:
        product_terms = collect_terms(template["product_groups"])
        product_expr = or_group(product_terms)
        fraud_expr = or_group(QUERY_GROUPS["fraud_terms"])
        org_expr = or_group(QUERY_GROUPS["enforcement_org_terms"])
        action_expr = or_group(QUERY_GROUPS["enforcement_action_terms"])
        if template["signal_mode"] == "fraud_and_enforcement":
            signal_expr = f"({fraud_expr} AND ({org_expr} OR {action_expr}))"
        elif template["signal_mode"] == "enforcement_only":
            signal_expr = f"({org_expr} OR {action_expr})"
        else:
            signal_expr = fraud_expr
        query = scoped_query(f"{product_expr} AND {signal_expr} AND language:en")
        rows.append(
            {
                "query_id": template["query_id"],
                "query_family": "boolean",
                "query": query,
                "product_groups": "; ".join(template["product_groups"]),
                "signal_mode": template["signal_mode"],
                "reason": template["reason"],
            }
        )
    return rows


def build_title_rows() -> list[dict[str, str]]:
    rows = []
    for template in TITLE_TEMPLATES:
        product_terms = collect_terms(template["product_groups"])
        signal_terms = collect_terms(template["signal_groups"])
        product_expr = or_group(product_terms, field="article_title")
        signal_expr = or_group(signal_terms, field="article_title")
        query = scoped_query(f"{product_expr} AND {signal_expr} AND language:en")
        rows.append(
            {
                "query_id": template["query_id"],
                "query_family": "title_only",
                "query": query,
                "product_groups": "; ".join(template["product_groups"]),
                "signal_mode": "; ".join(template["signal_groups"]),
                "reason": template["reason"],
            }
        )
    return rows


def build_proximity_rows() -> list[dict[str, str]]:
    rows = []
    for query_id, phrase, distance in PROXIMITY_TEMPLATES:
        query = scoped_query(f'"{phrase}"~{distance} AND language:en')
        rows.append(
            {
                "query_id": query_id,
                "query_family": "proximity",
                "query": query,
                "product_groups": "phrase_proximity",
                "signal_mode": f"within_{distance}_words",
                "reason": f'Find stories where "{phrase}" terms appear within {distance} words.',
            }
        )
    return rows


def collect_terms(group_names: list[str]) -> list[str]:
    terms = []
    for group_name in group_names:
        terms.extend(QUERY_GROUPS[group_name])
    return terms


def scoped_query(base_query: str) -> str:
    return f"({base_query}) AND NOT {or_group(QUERY_GROUPS['hard_exclusions'])}"


def or_group(terms: list[str], field: str | None = None) -> str:
    formatted = [format_field_term(field, term) if field else format_term(term) for term in terms]
    return "(" + " OR ".join(formatted) + ")"


def format_field_term(field: str | None, term: str) -> str:
    if not field:
        return format_term(term)
    return f"{field}:{format_term(term)}"


def format_term(term: str) -> str:
    if ":" in term or "*" in term:
        return term
    if " " in term or "-" in term:
        return f'"{term}"'
    return term


def write_seed_yaml(rows: list[dict[str, str]]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed_keywords": [row["query"] for row in rows],
        "query_rows": rows,
        "query_groups": QUERY_GROUPS,
        "india_collections": INDIA_COLLECTIONS,
        "notes": [
            "This is one combined run with boolean, title-only, and proximity query families.",
            "One Boolean family uses oil terms plus enforcement/evidence terms without requiring an explicit adulteration word.",
            "The NOT block uses human-approved Round 1 junk terms from irrelevant articles.",
            "Ghee and vanaspati remain hard out-of-scope exclusions.",
            "Media Cloud Boolean operators are capitalized and exact phrases are double quoted.",
        ],
    }
    SEED_YAML.parent.mkdir(parents=True, exist_ok=True)
    SEED_YAML.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def write_seed_csv(rows: list[dict[str, str]]) -> None:
    SEED_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "query_number",
        "query_id",
        "query_family",
        "query",
        "product_groups",
        "signal_mode",
        "reason",
        "date_start",
        "date_end",
        "collection_count",
        "hard_exclusion",
        "breadth",
    ]
    with SEED_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_config_yaml() -> None:
    run_rel = f"data/runs/{RUN_NAME}/mediacloud"
    output_rel = f"{run_rel}/outputs"
    config = {
        "date_range": {
            "start": DATE_START,
            "end": DATE_END,
        },
        "food_terms": QUERY_GROUPS["core_oils"] + QUERY_GROUPS["named_oils"],
        "adulteration_terms": [
            "adulterated",
            "adulteration",
            "contaminated",
            "contamination",
            "misbranded",
            "misbranding",
            "substandard",
            "spurious",
            "fake",
            "counterfeit",
            "unsafe",
            "rancid",
            "reused oil",
            "recycled oil",
            "mixed with",
        ],
        "action_terms": [
            "FSSAI",
            "FDA",
            "FSDA",
            "food safety",
            "food safety department",
            "food safety officer",
            "raid",
            "raids",
            "raided",
            "seized",
            "seizure",
            "samples collected",
            "sample collected",
            "samples sent",
            "lab test",
            "quality test",
            "prosecution",
            "penalty",
            "fine",
            "ban",
            "banned",
            "license suspended",
            "licence suspended",
            "shop sealed",
            "warehouse",
            "godown",
            "arrested",
            "crackdown",
            "inspection",
        ],
        "location_terms": [
            "India",
            "Indian",
            "Andhra Pradesh",
            "Arunachal Pradesh",
            "Assam",
            "Bihar",
            "Chandigarh",
            "Chhattisgarh",
            "Delhi",
            "Goa",
            "Gujarat",
            "Haryana",
            "Karnataka",
            "Kerala",
            "Madhya Pradesh",
            "Maharashtra",
            "Manipur",
            "Meghalaya",
            "Mizoram",
            "Nagaland",
            "Punjab",
            "Rajasthan",
            "Sikkim",
            "Tamil Nadu",
            "Tripura",
            "Uttar Pradesh",
            "Uttarakhand",
            "West Bengal",
        ],
        "discovery": {
            "enabled_sources": ["mediacloud"],
            "mediacloud": {
                "collection_ids": list(INDIA_COLLECTIONS.values()),
                "max_results": 1000,
                "delay_seconds": 1.5,
            },
        },
        "augmentation": {
            "seed_keywords_file": str(SEED_YAML.relative_to(ROOT)).replace("\\", "/"),
            "seed_keywords": [],
            "convergence_threshold": 0.85,
            "max_rounds": 5,
            "min_df": 2,
            "max_new_keywords": 30,
            "top_n_per_round": 20,
        },
        "crawl": {
            "delay_seconds": 3.0,
            "max_retries": 3,
            "backoff_factor": 2.0,
            "timeout_seconds": 30,
            "user_agent": (
                "FoodSafetyResearchBot/1.0 "
                "(Academic research on Indian edible oil food safety; contact: research@example.com)"
            ),
            "respect_robots_txt": True,
            "use_playwright": False,
        },
        "relevance": {
            "min_score_relevant": 0.55,
            "min_score_maybe": 0.25,
            "require_india_term": True,
            "require_oil_term": True,
            "require_adulteration_or_action_term": True,
            "weights": {
                "oil_term_hit": 0.25,
                "oil_term_cap": 0.30,
                "adulteration_term_hit": 0.20,
                "adulteration_term_cap": 0.25,
                "action_term_hit": 0.15,
                "action_term_cap": 0.20,
                "location_india_hit": 0.10,
                "location_state_hit": 0.05,
                "location_cap": 0.15,
                "date_in_range": 0.10,
            },
        },
        "dedupe": {
            "url_exact": True,
            "url_canonical": True,
            "title_normalize": True,
            "text_hash": True,
            "near_duplicate": {
                "enabled": True,
                "similarity_threshold": 0.75,
            },
        },
        "paths": {
            "seed_urls": f"data/runs/{RUN_NAME}/source_urls_from_docx.csv",
            "raw_html": f"{run_rel}/raw_html",
            "cleaned_text": f"{run_rel}/cleaned_text",
            "outputs": output_rel,
            "logs": f"{run_rel}/logs",
            "db": f"{output_rel}/articles.db",
            "discovered_urls": f"{output_rel}/discovered_urls.jsonl",
            "articles_jsonl": f"{output_rel}/articles.jsonl",
            "articles_csv": f"{output_rel}/articles.csv",
            "report": f"{output_rel}/report.json",
        },
        "api_keys": {
            "mediacloud_key": "",
            "google_cse_key": "",
            "google_cse_cx": "",
            "bing_api_key": "",
            "serpapi_key": "",
        },
    }
    CONFIG_YAML.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_YAML.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
