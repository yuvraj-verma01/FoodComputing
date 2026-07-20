#!/usr/bin/env python3
"""Convert a research CSV/Excel file into the Observatory's website schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd


REQUIRED = ["title", "url"]
EXTRACTION_FIELDS = [
    "llm_event_present", "llm_validator_label", "llm_confidence", "food_item",
    "adulterant_or_issue", "location_city", "location_district", "location_state",
    "latitude", "longitude", "quantity", "authority_or_evidence", "action_taken",
    "date_of_incident", "quadrant", "ontology_id", "ontology_category",
    "evidence_excerpt", "notes",
]
SCHEMA = [
    "article_id", "title", "source", "date", "url", "raw_text", "cleaned_text",
    "food_keyword", "human_label", "label_source", "review_status", "classifier_label",
    "classifier_score", "classifier_model", *EXTRACTION_FIELDS, "round_number", "is_demo",
]
ALIASES = {
    "publication_date": "date", "published_date": "date", "link": "url",
    "body": "raw_text", "text": "raw_text", "article_text": "cleaned_text",
    "keep": "human_label", "final_keep": "human_label", "label": "human_label",
    "score": "classifier_score", "model": "classifier_model",
}


def standard_name(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return ALIASES.get(value, value)


def missing(series: pd.Series) -> pd.Series:
    normal = series.astype("string").str.strip().str.lower()
    return series.isna() | normal.isin(["", "nan", "null", "none", "n/a", "na"])


def stable_id(row: pd.Series) -> str:
    value = str(row.get("url") or row.get("title") or "").strip()
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:24]


def load(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, low_memory=False)
    raise ValueError("Input must be .csv, .xlsx or .xls")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-csv", type=Path, default=Path("data/articles.csv"))
    parser.add_argument("--output-json", type=Path, default=Path("data/articles.json"))
    parser.add_argument("--report", type=Path, default=Path("data/data-quality-report.json"))
    args = parser.parse_args()

    original = load(args.input)
    frame = original.copy(deep=True)
    frame.columns = [standard_name(str(column)) for column in frame.columns]
    frame = frame.loc[:, ~frame.columns.duplicated(keep="first")]

    absent_required = [column for column in REQUIRED if column not in frame.columns]
    if absent_required:
        raise ValueError(f"Missing required columns: {', '.join(absent_required)}")

    for column in SCHEMA:
        if column not in frame.columns:
            frame[column] = ""
    id_missing = missing(frame["article_id"])
    frame.loc[id_missing, "article_id"] = frame.loc[id_missing].apply(stable_id, axis=1)

    duplicate_ids = frame["article_id"].duplicated(keep="first")
    duplicate_urls = frame["url"].astype("string").str.strip().duplicated(keep=False) & ~missing(frame["url"])
    frame["duplicate_url"] = duplicate_urls
    frame = frame.loc[~duplicate_ids, SCHEMA + ["duplicate_url"]].copy()

    missingness = {
        column: {"missing": int(missing(frame[column]).sum()), "percent": round(float(missing(frame[column]).mean() * 100), 2)}
        for column in EXTRACTION_FIELDS
    }
    report = {
        "input_file": str(args.input.resolve()),
        "input_rows": len(original),
        "output_rows": len(frame),
        "duplicate_article_ids_removed": int(duplicate_ids.sum()),
        "rows_with_duplicate_urls": int(duplicate_urls.sum()),
        "missing_required_columns": absent_required,
        "extraction_field_missingness": missingness,
        "original_file_modified": False,
    }

    for output in [args.output_csv, args.output_json, args.report]:
        output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output_csv, index=False, encoding="utf-8")
    args.output_json.write_text(frame.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
