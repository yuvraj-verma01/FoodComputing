"""Build MediaCloud seed queries for ghee adulteration Round 1.

The structure mirrors the edible-oil combined query run: phrase, title-only,
proximity, and Boolean families in one query plan. This file intentionally uses
only the human-approved ghee keyword set.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
RUN_NAME = "ghee_adulteration_round_01_2026-06-30"
RUN_DIR = ROOT / "data" / "runs" / RUN_NAME
SEED_YAML = ROOT / "config" / "ghee_round1_seed_queries.yaml"
CONFIG_YAML = ROOT / "config" / "config_ghee_round1.yaml"
SEED_CSV = RUN_DIR / "proposed_mediacloud_ghee_round1_seed_queries.csv"

DATE_START = "2021-01-01"
DATE_END = "2026-06-30"


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
    "ghee_products": [
        "ghee",
        "cow ghee",
        "desi ghee",
        "pure ghee",
        "loose ghee",
        "fake ghee",
        "fake cow ghee",
        "adulterated ghee",
        "suspected adulterated ghee",
        "vegetable ghee",
        "ghee racket",
        "ghee racket busted",
    ],
    "ghee_core_products": [
        "ghee",
        "cow ghee",
        "desi ghee",
        "pure ghee",
        "loose ghee",
    ],
    "ghee_incident_phrases": [
        "fake ghee",
        "fake cow ghee",
        "adulterated ghee",
        "suspected adulterated ghee",
        "ghee racket",
        "ghee racket busted",
    ],
    "adulterated_fake_terms": [
        "adulterated",
        "fake",
    ],
    "ghee_adulterant_terms": [
        "vanaspati",
        "vegetable ghee",
    ],
    "enforcement_org_terms": [
        "fssai",
        "fda",
        "food safety",
    ],
    "enforcement_action_terms": [
        "raid",
        "seized",
    ],
}


PHRASE_TEMPLATES = [
    ("phrase_adulterated_ghee", "adulterated ghee", "Direct phrase query from human-approved ghee keywords."),
    ("phrase_fake_ghee", "fake ghee", "Direct phrase query from human-approved ghee keywords."),
    ("phrase_fake_cow_ghee", "fake cow ghee", "Direct phrase query from human-approved ghee keywords."),
    (
        "phrase_suspected_adulterated_ghee",
        "suspected adulterated ghee",
        "Direct phrase query retained after human review.",
    ),
    ("phrase_ghee_racket", "ghee racket", "Direct phrase query retained after human review."),
    ("phrase_ghee_racket_busted", "ghee racket busted", "Direct phrase query retained after human review."),
    ("phrase_vegetable_ghee", "vegetable ghee", "Adulterant/context phrase retained after human review."),
]


BOOLEAN_TEMPLATES = [
    {
        "query_id": "boolean_ghee_products_adulterated_fake",
        "product_groups": ["ghee_core_products"],
        "signal_mode": "adulterated_fake_only",
        "reason": "Ghee product terms co-occur with approved adulterated/fake terms.",
    },
    {
        "query_id": "boolean_ghee_incident_phrases",
        "product_groups": ["ghee_incident_phrases"],
        "signal_mode": "phrase_only",
        "reason": "Human-approved ghee incident phrases are already precise enough for discovery.",
    },
    {
        "query_id": "boolean_ghee_products_enforcement",
        "product_groups": ["ghee_core_products"],
        "signal_mode": "enforcement_only",
        "reason": "Ghee terms plus enforcement/evidence language for raid/seizure/lab-test stories.",
    },
    {
        "query_id": "boolean_ghee_products_adulterated_fake_enforcement",
        "product_groups": ["ghee_core_products"],
        "signal_mode": "adulterated_fake_and_enforcement",
        "reason": "Ghee terms plus approved adulterated/fake and enforcement terms.",
    },
    {
        "query_id": "boolean_ghee_adulterants_context",
        "product_groups": ["ghee_core_products"],
        "signal_mode": "adulterant_context",
        "reason": "Human-approved adulterant/context terms only when ghee is also present.",
    },
]


TITLE_TEMPLATES = [
    {
        "query_id": "title_ghee_products_adulterated_fake",
        "product_groups": ["ghee_core_products"],
        "signal_groups": ["adulterated_fake_terms"],
        "reason": "Ghee product term and approved adulterated/fake term both appear in the title.",
    },
    {
        "query_id": "title_ghee_incident_phrases",
        "product_groups": ["ghee_incident_phrases"],
        "signal_groups": [],
        "reason": "Human-approved ghee incident phrase appears in the title.",
    },
    {
        "query_id": "title_ghee_enforcement",
        "product_groups": ["ghee_core_products"],
        "signal_groups": ["enforcement_org_terms", "enforcement_action_terms"],
        "reason": "Ghee product term and enforcement/evidence term both appear in the title.",
    },
]


PROXIMITY_TEMPLATES = [
    ("proximity_ghee_adulterated", "ghee adulterated", 10),
    ("proximity_ghee_fake", "ghee fake", 8),
    ("proximity_ghee_seized", "ghee seized", 10),
    ("proximity_ghee_raid", "ghee raid", 10),
    ("proximity_ghee_food_safety", "ghee food safety", 10),
    ("proximity_ghee_fssai", "ghee fssai", 10),
    ("proximity_ghee_fda", "ghee fda", 10),
    ("proximity_cow_ghee_fake", "cow ghee fake", 8),
    ("proximity_cow_ghee_adulterated", "cow ghee adulterated", 10),
    ("proximity_desi_ghee_adulterated", "desi ghee adulterated", 10),
    ("proximity_loose_ghee_seized", "loose ghee seized", 10),
    ("proximity_ghee_vanaspati", "ghee vanaspati", 10),
    ("proximity_ghee_vegetable_ghee", "ghee vegetable ghee", 10),
    ("proximity_suspected_adulterated_ghee", "suspected adulterated ghee", 10),
    ("proximity_ghee_racket", "ghee racket", 10),
    ("proximity_ghee_racket_busted", "ghee racket busted", 10),
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
                "date_start": DATE_START,
                "date_end": DATE_END,
            },
            indent=2,
        )
    )
    return 0


def build_queries() -> list[dict[str, str]]:
    rows = []
    rows.extend(build_phrase_rows())
    rows.extend(build_boolean_rows())
    rows.extend(build_title_rows())
    rows.extend(build_proximity_rows())
    seen = set()
    unique_rows = []
    for row in rows:
        if row["query"] in seen:
            continue
        seen.add(row["query"])
        unique_rows.append(row)
    for index, row in enumerate(unique_rows, start=1):
        row["query_number"] = str(index)
        row["date_start"] = DATE_START
        row["date_end"] = DATE_END
        row["collection_count"] = str(len(INDIA_COLLECTIONS))
        row["hard_exclusion"] = ""
        row["breadth"] = "combined_phrase_boolean_title_proximity"
    return unique_rows


def build_phrase_rows() -> list[dict[str, str]]:
    rows = []
    for query_id, phrase, reason in PHRASE_TEMPLATES:
        rows.append(
            {
                "query_id": query_id,
                "query_family": "phrase",
                "query": scoped_query(f"{format_term(phrase)} AND language:en"),
                "product_groups": "human_approved_phrase",
                "signal_mode": "exact_phrase",
                "reason": reason,
            }
        )
    return rows


def build_boolean_rows() -> list[dict[str, str]]:
    rows = []
    for template in BOOLEAN_TEMPLATES:
        product_terms = collect_terms(template["product_groups"])
        product_expr = or_group(product_terms)
        adulterated_fake_expr = or_group(QUERY_GROUPS["adulterated_fake_terms"])
        org_expr = or_group(QUERY_GROUPS["enforcement_org_terms"])
        action_expr = or_group(QUERY_GROUPS["enforcement_action_terms"])
        adulterant_expr = or_group(QUERY_GROUPS["ghee_adulterant_terms"])
        mode = template["signal_mode"]
        if mode == "phrase_only":
            base_query = f"{product_expr} AND language:en"
        elif mode == "adulterated_fake_and_enforcement":
            base_query = f"{product_expr} AND {adulterated_fake_expr} AND ({org_expr} OR {action_expr}) AND language:en"
        elif mode == "enforcement_only":
            base_query = f"{product_expr} AND ({org_expr} OR {action_expr}) AND language:en"
        elif mode == "adulterant_context":
            base_query = f"{product_expr} AND {adulterant_expr} AND ({adulterated_fake_expr} OR {org_expr} OR {action_expr}) AND language:en"
        else:
            base_query = f"{product_expr} AND {adulterated_fake_expr} AND language:en"
        rows.append(
            {
                "query_id": template["query_id"],
                "query_family": "boolean",
                "query": scoped_query(base_query),
                "product_groups": "; ".join(template["product_groups"]),
                "signal_mode": mode,
                "reason": template["reason"],
            }
        )
    return rows


def build_title_rows() -> list[dict[str, str]]:
    rows = []
    for template in TITLE_TEMPLATES:
        product_terms = collect_terms(template["product_groups"])
        product_expr = or_group(product_terms, field="article_title")
        if template["signal_groups"]:
            signal_terms = collect_terms(template["signal_groups"])
            signal_expr = or_group(signal_terms, field="article_title")
            base_query = f"{product_expr} AND {signal_expr} AND language:en"
            signal_mode = "; ".join(template["signal_groups"])
        else:
            base_query = f"{product_expr} AND language:en"
            signal_mode = "exact_title_phrase"
        rows.append(
            {
                "query_id": template["query_id"],
                "query_family": "title_only",
                "query": scoped_query(base_query),
                "product_groups": "; ".join(template["product_groups"]),
                "signal_mode": signal_mode,
                "reason": template["reason"],
            }
        )
    return rows


def build_proximity_rows() -> list[dict[str, str]]:
    rows = []
    for query_id, phrase, distance in PROXIMITY_TEMPLATES:
        rows.append(
            {
                "query_id": query_id,
                "query_family": "proximity",
                "query": scoped_query(f'"{phrase}"~{distance} AND language:en'),
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
    return f"({base_query})"


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
            "Ghee Round 1 follows the edible-oil workflow with phrase, boolean, title-only, and proximity families.",
            "This query set uses only human-approved ghee keywords.",
            "Broad enforcement terms such as seized/FDA/FSSAI are combine-only, never standalone.",
            "Media Cloud Boolean operators are capitalized and exact phrases are double quoted.",
            "Date range starts at 2021-01-01, matching the oil workflow.",
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
        "food_terms": QUERY_GROUPS["ghee_products"],
        "adulteration_terms": [
            "adulterated",
            "fake",
        ],
        "adulterant_terms": QUERY_GROUPS["ghee_adulterant_terms"],
        "action_terms": [
            "fssai",
            "fda",
            "food safety",
            "raid",
            "seized",
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
            "timeout_seconds": 45,
            "user_agent": (
                "FoodSafetyResearchBot/1.0 "
                "(Academic research on Indian ghee food safety; contact: research@example.com)"
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
