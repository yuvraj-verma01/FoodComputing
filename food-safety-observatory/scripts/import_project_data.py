#!/usr/bin/env python3
"""Build the website dataset from the current oil and ghee research outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
DATA_DIR = APP_ROOT / "data"

OIL_CORPUS = REPO_ROOT / "YUVRAJ/outputs/edible_oil/master_corpus/master_all_articles.csv"
OIL_PREDICTIONS = REPO_ROOT / "news_crawler/reports/model_training_cleaned/cross_validation_predictions.csv"
GHEE_CORPUS = REPO_ROOT / "YUVRAJ/outputs/ghee/round_01_fulltext_llm_review/ghee_relevance_fulltext/ghee_fulltext_llm_scored_articles.csv"
GHEE_REVIEW = REPO_ROOT / "news_crawler/data/runs/ghee_adulteration_round_01_2026-06-30/mediacloud/outputs/ghee_relevance_fulltext/ghee_fulltext_llm_review.xlsx"
GHEE_TRANSFER = REPO_ROOT / "news_crawler/reports/ghee_transfer_test/ghee_transfer_predictions.csv"

WINNING_MODEL = "ens_wavg[tfidf_linsvm/full+bge-large_rbfsvm/oilemb+roberta-base_lead_512/full|0.17,0.67,0.17]"

SCHEMA = [
    "article_id", "title", "source", "date", "url", "raw_text", "cleaned_text",
    "food_keyword", "human_label", "label_source", "review_status", "classifier_label",
    "classifier_score", "classifier_model", "llm_event_present", "llm_validator_label",
    "llm_confidence", "food_item", "adulterant_or_issue", "location_city",
    "location_district", "location_state", "latitude", "longitude", "quantity",
    "authority_or_evidence", "action_taken", "date_of_incident", "quadrant",
    "ontology_id", "ontology_category", "evidence_excerpt", "notes", "round_number",
    "is_demo",
]


def text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def label(value: object) -> str:
    value = text(value).lower()
    if value in {"1", "1.0", "relevant", "true", "yes"}:
        return "relevant"
    if value in {"0", "0.0", "irrelevant", "false", "no"}:
        return "irrelevant"
    return ""


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha1(value.encode('utf-8')).hexdigest()[:20]}"


def read_article_text(file_path: object) -> str:
    candidate = Path(text(file_path))
    if not candidate.is_file():
        return ""
    try:
        return candidate.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def blank_record() -> dict[str, object]:
    return {column: "" for column in SCHEMA} | {"is_demo": False}


def build_oil_records() -> list[dict[str, object]]:
    corpus = pd.read_csv(OIL_CORPUS, low_memory=False)
    predictions = pd.read_csv(OIL_PREDICTIONS, low_memory=False)
    predictions = predictions[predictions["model_name"] == WINNING_MODEL]
    by_id = predictions.drop_duplicates("article_id").set_index("article_id").to_dict("index")
    records: list[dict[str, object]] = []

    for _, row in corpus.iterrows():
        article_id = text(row.get("article_id")) or stable_id("oil", text(row.get("url")) or text(row.get("title")))
        prediction = by_id.get(article_id, {})
        human_label = label(row.get("final_keep"))
        record = blank_record()
        record.update({
            "article_id": article_id,
            "title": text(row.get("title")),
            "source": text(row.get("source")) or text(row.get("domain")),
            "date": text(row.get("date")) or text(row.get("publication_date")),
            "url": text(row.get("url")),
            "cleaned_text": text(row.get("article_text")),
            "food_keyword": "Edible Oil",
            "human_label": human_label,
            "label_source": text(row.get("human_review_source")) or "edible-oil master corpus",
            "review_status": "reviewed" if human_label else "pending",
            "classifier_label": label(prediction.get("predicted_label")),
            "classifier_score": prediction.get("predicted_probability", ""),
            "classifier_model": WINNING_MODEL if prediction else "",
            "round_number": text(row.get("round_number")),
            "notes": "Cross-validated prediction from the final edible-oil ensemble." if prediction else "",
        })
        records.append(record)
    return records


def build_ghee_records() -> list[dict[str, object]]:
    corpus = pd.read_csv(GHEE_CORPUS, low_memory=False)
    review = pd.read_excel(GHEE_REVIEW)
    transfer = pd.read_csv(GHEE_TRANSFER, low_memory=False)
    review_by_url = review.drop_duplicates("url").set_index("url")["keep"].to_dict()
    transfer_by_url = transfer.drop_duplicates("url").set_index("url").to_dict("index")
    records: list[dict[str, object]] = []

    for _, row in corpus.iterrows():
        url = text(row.get("url"))
        human_label = label(review_by_url.get(url))
        prediction = transfer_by_url.get(url, {})
        score = prediction.get("proba_ensemble1", "")
        classifier_label = ""
        if score != "" and not pd.isna(score):
            classifier_label = "relevant" if float(score) >= 0.5 else "irrelevant"
        record = blank_record()
        record.update({
            "article_id": stable_id("ghee", url or text(row.get("title"))),
            "title": text(row.get("title")),
            "source": text(row.get("source")),
            "date": text(row.get("date")),
            "url": url,
            "cleaned_text": read_article_text(row.get("file_path")),
            "food_keyword": "Ghee",
            "human_label": human_label,
            "label_source": "manual ghee review workbook" if human_label else "",
            "review_status": "reviewed" if human_label else "pending",
            "classifier_label": classifier_label,
            "classifier_score": score,
            "classifier_model": "edible-oil winning ensemble (unchanged transfer test)" if prediction else "",
            "round_number": "1",
            "notes": "Out-of-domain transfer result at the oil threshold; not a ghee-specific classifier." if prediction else "",
        })
        records.append(record)
    return records


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    records = build_oil_records() + build_ghee_records()
    frame = pd.DataFrame(records, columns=SCHEMA)
    frame.to_csv(DATA_DIR / "articles.csv", index=False, encoding="utf-8")

    report = {
        "generated_from_project_outputs": True,
        "total_records": len(frame),
        "by_food_category": frame["food_keyword"].value_counts().to_dict(),
        "human_labels": frame["human_label"].replace("", "pending").value_counts().to_dict(),
        "classifier_scored": int(frame["classifier_score"].notna().sum() - (frame["classifier_score"] == "").sum()),
        "local_llm_relevance_fields_included": False,
        "future_llm_validator_fields_populated": False,
    }
    (DATA_DIR / "current-data-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
