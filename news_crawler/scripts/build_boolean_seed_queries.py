"""Build precise Media Cloud Boolean seed queries for edible-oil discovery.

Edit the dictionaries below to change query behavior. Outputs are written to
config/ and the fresh Boolean run folder.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / "data" / "runs" / "edible_oils_boolean_2026-06-21"
SEED_YAML = ROOT / "config" / "edible_oil_boolean_seed_queries.yaml"
SEED_CSV = RUN_DIR / "proposed_mediacloud_boolean_seed_queries.csv"


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
    "junk_terms": [
        "recruitment",
        "vacancy",
        "job*",
        "exam",
        "admit card",
        "answer key",
        "syllabus",
        "eat right",
        "fortification",
        "fortified",
        "trans fat",
        "health claims",
        "zero maida",
        "organic label",
        "misleading claims",
        "consumer complaints",
        "stock market",
        "crude oil",
        "petrol",
        "diesel",
        "engine oil",
        "essential oil",
        "hair oil",
        "massage oil",
    ],
}


QUERY_TEMPLATES = [
    {
        "query_id": "core_oils_fraud_strict",
        "product_groups": ["core_oils"],
        "signal_mode": "fraud_only",
        "reason": "Core edible/cooking oil phrases must co-occur with direct adulteration/fraud terms.",
    },
    {
        "query_id": "named_oils_fraud_strict",
        "product_groups": ["named_oils"],
        "signal_mode": "fraud_only",
        "reason": "Specific oil types must co-occur with direct adulteration/fraud terms.",
    },
    {
        "query_id": "oils_enforcement_evidence_strict",
        "product_groups": ["core_oils", "named_oils"],
        "signal_mode": "fraud_and_enforcement_action",
        "reason": "Oil terms plus both enforcement/action language and adulteration/fraud language.",
    },
]


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    queries = build_queries()
    write_seed_yaml(queries)
    write_seed_csv(queries)
    print(json.dumps({"queries": len(queries), "seed_yaml": str(SEED_YAML), "seed_csv": str(SEED_CSV)}, indent=2))
    return 0


def build_queries() -> list[dict[str, str]]:
    rows = []
    for template in QUERY_TEMPLATES:
        product_terms = []
        for group_name in template["product_groups"]:
            product_terms.extend(QUERY_GROUPS[group_name])
        product_expr = or_group(product_terms)
        fraud_expr = or_group(QUERY_GROUPS["fraud_terms"])
        org_expr = or_group(QUERY_GROUPS["enforcement_org_terms"])
        action_expr = or_group(QUERY_GROUPS["enforcement_action_terms"])
        junk_expr = or_group(QUERY_GROUPS["junk_terms"])
        if template["signal_mode"] == "fraud_and_enforcement_action":
            signal_expr = f"({fraud_expr} AND ({org_expr} OR {action_expr}))"
        else:
            signal_expr = fraud_expr
        query = f"({product_expr} AND {signal_expr} AND language:en) NOT {junk_expr}"
        rows.append(
            {
                "query_id": template["query_id"],
                "query": query,
                "product_groups": "; ".join(template["product_groups"]),
                "signal_mode": template["signal_mode"],
                "reason": template["reason"],
                "date_start": "2021-01-01",
                "date_end": "2026-06-21",
                "collection_count": str(len(INDIA_COLLECTIONS)),
                "permutation_scope": "boolean_group_query_not_all_permutations",
            }
        )
    return rows


def or_group(terms: list[str]) -> str:
    return "(" + " OR ".join(format_term(term) for term in terms) + ")"


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
            "Media Cloud Boolean operators must be capitalized.",
            "Exact phrases are double quoted.",
            "Wildcard stems are used only where useful.",
            "The NOT group removes recurring garbage classes from the previous noisy run.",
        ],
    }
    SEED_YAML.parent.mkdir(parents=True, exist_ok=True)
    SEED_YAML.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_seed_csv(rows: list[dict[str, str]]) -> None:
    SEED_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SEED_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
