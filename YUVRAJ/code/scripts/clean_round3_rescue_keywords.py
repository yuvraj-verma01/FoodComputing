from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KEYWORDS = (
    ROOT
    / "reports"
    / "edible_oil_adulteration_round_02"
    / "round_03_keyword_review"
    / "round_03_from_round_02_rescue_keyword_candidates.csv"
)
DEFAULT_SOURCE = (
    ROOT
    / "data"
    / "runs"
    / "edible_oil_adulteration_round_02_2026-06-23"
    / "mediacloud"
    / "outputs"
    / "oil_relevance"
    / "metadata_rescue_fulltext_added.csv"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "reports"
    / "edible_oil_adulteration_round_02"
    / "round_03_keyword_review"
)


MANUAL_REVIEW_TERMS = [
    {
        "keyword_or_keyphrase": "palm olein oil",
        "category": "oil/product",
        "review_label": "manual_review",
        "review_reason": "spaced spelling variant of palmolein found in a new relevant article title",
        "query_role": "product_variant",
    },
    {
        "keyword_or_keyphrase": "tainted edible oil",
        "category": "adulteration/fraud",
        "review_label": "keep_core",
        "review_reason": "direct edible-oil safety/adulteration phrase from a new relevant article title",
        "query_role": "fraud_signal",
    },
    {
        "keyword_or_keyphrase": "unfit edible oil",
        "category": "adulteration/fraud",
        "review_label": "keep_core",
        "review_reason": "direct edible-oil safety phrase from a new relevant article body",
        "query_role": "fraud_signal",
    },
    {
        "keyword_or_keyphrase": "dropsy deaths",
        "category": "health/adulterant signal",
        "review_label": "manual_review",
        "review_reason": "health-outcome phrase tied to argemone/mustard-oil adulteration in a new relevant article",
        "query_role": "health_outcome",
    },
    {
        "keyword_or_keyphrase": "adulteration of sunflower oil",
        "category": "adulteration/fraud",
        "review_label": "manual_review",
        "review_reason": "specific oil-plus-adulteration phrase from a new relevant article",
        "query_role": "fraud_signal",
    },
    {
        "keyword_or_keyphrase": "mislabelled oils",
        "category": "adulteration/fraud",
        "review_label": "keep_core",
        "review_reason": "direct edible-oil mislabelling phrase from a new relevant article title",
        "query_role": "fraud_signal",
    },
    {
        "keyword_or_keyphrase": "fortification logo",
        "category": "adulteration/fraud",
        "review_label": "manual_review",
        "review_reason": "label-fraud phrase from articles where oil carried a fortification logo without fortification",
        "query_role": "fraud_signal",
    },
    {
        "keyword_or_keyphrase": "without actual fortification",
        "category": "adulteration/fraud",
        "review_label": "manual_review",
        "review_reason": "fortification-fraud phrase from a new relevant edible-oil article",
        "query_role": "fraud_signal",
    },
    {
        "keyword_or_keyphrase": "labelling violations",
        "category": "adulteration/fraud",
        "review_label": "manual_review",
        "review_reason": "mislabelling/food-fraud phrase from a new relevant edible-oil article",
        "query_role": "fraud_signal",
    },
]


NEAR_DUPLICATE_REASONS = {
    "refined soybean oil": "covered by existing terms: refined oil + soybean oil",
    "palmolein oil": "covered by existing term: palmolein",
    "refined palmolein oil": "covered by existing terms: refined oil + palmolein",
    "fda officials": "covered by existing terms: FDA + food safety officials",
    "food safety and drug": "covered by existing terms: food safety + FDA/FSDA",
    "fda found": "fragment covered by FDA",
    "budh nagar food safety": "local fragment covered by food safety",
    "nagar food safety authorities": "local fragment covered by food safety",
    "fda officials seized": "covered by existing terms: FDA + seized",
    "nagar food safety": "local fragment covered by food safety",
    "fda food": "fragment covered by FDA",
    "fda officials seized shrikhand": "mixed-food fragment, not an edible-oil query concept",
    "food safety officer suresh": "named-person fragment covered by food safety officer",
    "fda food inspectors": "covered by existing terms: FDA + food safety officials",
    "food safety raids": "covered by existing terms: food safety + raids",
    "fda conducted operations": "fragment covered by FDA + raid/seized terms",
    "lakhs seized sources revealed": "news-writing fragment, not a query concept",
    "worth lakhs seized sources": "news-writing fragment, not a query concept",
    "food safety authorities": "covered by existing term: food safety",
    "fda officials raided": "covered by existing terms: FDA + raided",
    "raids conducted": "covered by existing term: raids",
}

NOISY_BROAD_TERMS = {
    "adulterated food items": "broad food-adulteration term; not oil-specific enough for Round 3",
    "adulterated food": "broad food-adulteration term; not oil-specific enough for Round 3",
    "food adulteration": "broad food-adulteration term already represented by adulteration + oil terms",
    "seized adulterated food items": "broad mixed-food phrase; use existing seized/adulterated terms with oil terms",
    "seizing adulterated food items": "broad mixed-food phrase; use existing seized/adulterated terms with oil terms",
    "seized adulterated food": "broad mixed-food phrase; use existing seized/adulterated terms with oil terms",
    "seizing adulterated food": "broad mixed-food phrase; use existing seized/adulterated terms with oil terms",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a compact Round 3 keyword review set from new Round 2 rescue articles."
    )
    parser.add_argument("--keywords", type=Path, default=DEFAULT_KEYWORDS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_keyword(term: str) -> str:
    text = (term or "").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = []
    for word in text.split():
        if len(word) > 4 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        words.append(word)
    return " ".join(words)


def source_rows(path: Path) -> list[dict[str, str]]:
    return [
        row
        for row in read_csv(path)
        if row.get("final_keep") == "1" and (row.get("article_text") or "").strip()
    ]


def count_occurrences(term: str, rows: list[dict[str, str]]) -> tuple[int, int]:
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    total = 0
    docs = 0
    for row in rows:
        text = " ".join([row.get("title", ""), row.get("article_text", "")])
        matches = pattern.findall(text)
        if matches:
            docs += 1
            total += len(matches)
    return total, docs


def first_context(term: str, rows: list[dict[str, str]]) -> dict[str, str]:
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    for index, row in enumerate(rows, start=1):
        text = " ".join([row.get("title", ""), row.get("article_text", "")])
        match = pattern.search(text)
        if not match:
            continue
        start = max(0, match.start() - 130)
        end = min(len(text), match.end() + 130)
        context = text[start:end].replace("\n", " ").strip()
        if start > 0:
            context = "..." + context
        if end < len(text):
            context += "..."
        return {
            "example_article_number": str(index),
            "example_article_title": row.get("title", ""),
            "example_url": row.get("url", ""),
            "example_domain": row.get("domain", ""),
            "example_source": row.get("source", ""),
            "example_publication_date": row.get("publication_date", ""),
            "example_human_label": row.get("final_human_label", ""),
            "example_word_count": row.get("word_count", ""),
            "example_article_id": row.get("article_id", ""),
            "example_context": context,
        }
    return {
        "example_article_number": "",
        "example_article_title": "",
        "example_url": "",
        "example_domain": "",
        "example_source": "",
        "example_publication_date": "",
        "example_human_label": "",
        "example_word_count": "",
        "example_article_id": "",
        "example_context": "",
    }


def build_manual_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    clean_rows: list[dict[str, Any]] = []
    for item in MANUAL_REVIEW_TERMS:
        term = item["keyword_or_keyphrase"]
        total, docs = count_occurrences(term, rows)
        context = first_context(term, rows)
        clean_rows.append(
            {
                "keyword_or_keyphrase": term,
                "methods_found": "manual_article_read",
                "method_count": 1,
                "method_agreement_score": "",
                "total_frequency": total,
                "document_frequency": docs,
                "tfidf_score_normalized": "",
                "yake_score_normalized": "",
                "frequency_score_normalized": "",
                "document_frequency_score": "",
                "composite_score": "",
                "category": item["category"],
                "review_label": item["review_label"],
                "review_reason": item["review_reason"],
                "source_round_number": 2,
                "next_round_target": 3,
                "keyword_source_scope": "manual_cleanup_from_new_unique_round_02_rescue_relevant_articles_only",
                "keyword_source_article_count": len(rows),
                "query_role": item["query_role"],
                "normalized_keyword": normalize_keyword(term),
                **context,
            }
        )
    return clean_rows


def suppress_raw_candidates(raw_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    suppressed: list[dict[str, Any]] = []
    for row in raw_rows:
        term = row.get("keyword_or_keyphrase", "")
        norm = normalize_keyword(term)
        reason = ""
        if row.get("review_label") == "drop":
            reason = "extractor_label_drop"
        elif norm in NEAR_DUPLICATE_REASONS:
            reason = f"near_duplicate: {NEAR_DUPLICATE_REASONS[norm]}"
        elif norm in NOISY_BROAD_TERMS:
            reason = f"broad_or_noisy: {NOISY_BROAD_TERMS[norm]}"
        elif row.get("category") == "location":
            reason = "location_only_not_needed_for_round3_queries"
        else:
            reason = "not_selected_after_manual_cleanup"
        suppressed.append(
            {
                **row,
                "normalized_keyword": norm,
                "suppression_reason": reason,
            }
        )
    return suppressed


def main() -> int:
    args = parse_args()
    raw_rows = read_csv(args.keywords)
    relevant_rows = source_rows(args.source)

    clean_rows = build_manual_rows(relevant_rows)
    suppressed_rows = suppress_raw_candidates(raw_rows)

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    clean_csv = out / "round_03_from_round_02_rescue_keyword_candidates_clean.csv"
    suppressed_csv = out / "round_03_from_round_02_rescue_keyword_candidates_suppressed.csv"
    summary_json = out / "round_03_from_round_02_rescue_keyword_cleanup_summary.json"

    write_csv(clean_csv, clean_rows)
    write_csv(suppressed_csv, suppressed_rows)

    summary = {
        "created_at": utc_now(),
        "source_keyword_candidates": str(args.keywords),
        "source_articles": str(args.source),
        "source_scope": "new unique Round 2 metadata-rescue relevant articles only",
        "raw_candidate_count_after_exact_prior_filter": len(raw_rows),
        "clean_review_candidate_count": len(clean_rows),
        "suppressed_candidate_count": len(suppressed_rows),
        "clean_review_label_counts": dict(Counter(row.get("review_label", "") for row in clean_rows)),
        "clean_category_counts": dict(Counter(row.get("category", "") for row in clean_rows)),
        "suppression_reason_counts": dict(
            Counter(row.get("suppression_reason", "") for row in suppressed_rows)
        ),
        "note": (
            "The clean workbook intentionally removes exact prior keywords, near-duplicate "
            "variants, location-only terms, and broad mixed-food fragments. Raw candidates "
            "are retained in the suppressed CSV for audit."
        ),
        "outputs": {
            "clean_candidates_csv": str(clean_csv),
            "suppressed_candidates_csv": str(suppressed_csv),
            "review_workbook": str(out / "round_03_from_round_02_rescue_keyword_review_clean.xlsx"),
        },
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
