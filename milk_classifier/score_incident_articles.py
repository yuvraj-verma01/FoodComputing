#!/usr/bin/env python3
"""Train the selected Milk relevance model and score published Milk incidents.

The evaluation workbook supplies the exact 1,384-row labeled corpus used by the
winning full-text TF-IDF + calibrated LinearSVC experiment. This script fits a
deployment model on that full corpus, scores every published Milk incident, and
updates the website's JSON and article-level CSV exports together.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


MODEL_NAME = "milk_relevance_tfidf_calibrated_linsvc_fulltext_v1"
PREDICTIONS_SHEET = "Best Model Predictions"
METRICS_SHEET = "Model Metrics Comparison"
EXPECTED_TRAINING_ROWS = 1_384


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--model-output", required=True, type=Path)
    parser.add_argument("--audit-output", required=True, type=Path)
    parser.add_argument("--prediction-date", default=date.today().isoformat())
    return parser.parse_args()


def full_text(title: object, body: object) -> str:
    return f"{str(title).strip()}\n\n{str(body).strip()}".strip()


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "vectorizer",
                TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.9),
            ),
            (
                "classifier",
                CalibratedClassifierCV(
                    LinearSVC(
                        class_weight="balanced",
                        random_state=42,
                        max_iter=10_000,
                    ),
                    cv=5,
                ),
            ),
        ]
    )


def load_training_data(workbook: Path) -> tuple[list[str], np.ndarray, dict]:
    metrics = pd.read_excel(workbook, sheet_name=METRICS_SHEET)
    winning = metrics.iloc[0]
    if winning["Model Name"] != "TF-IDF + Calibrated LinearSVC":
        raise ValueError("The first metrics row is not the documented winning model")
    if winning["Representation"] != "title_plus_body_full":
        raise ValueError("The winning model does not use the documented full-text representation")

    frame = pd.read_excel(workbook, sheet_name=PREDICTIONS_SHEET)
    required = {"title", "article_text", "true_label"}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Training sheet is missing columns: {sorted(missing)}")
    if len(frame) != EXPECTED_TRAINING_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_TRAINING_ROWS} training rows, found {len(frame)}"
        )
    if frame[list(required)].isna().any().any():
        raise ValueError("Training title, body, or label contains missing values")

    labels = frame["true_label"].astype(int).to_numpy()
    if set(labels) != {0, 1}:
        raise ValueError(f"Expected binary labels, found {sorted(set(labels))}")
    texts = [full_text(title, body) for title, body in zip(frame["title"], frame["article_text"])]
    evaluation = {
        "method": "5-fold out-of-fold evaluation",
        "f1": float(winning["F1-Score"]),
        "precision": float(winning["Precision"]),
        "recall": float(winning["Recall"]),
        "roc_auc": float(winning["ROC-AUC"]),
        "pr_auc": float(winning["PR-AUC"]),
        "accuracy": float(winning["Accuracy"]),
    }
    return texts, labels, evaluation


def load_dataset(data_dir: Path) -> dict:
    path = data_dir / "incident-events.json"
    with path.open(encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload.get("incidents"), list):
        raise ValueError(f"Invalid incident dataset: {path}")
    return payload


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def update_article_csv(data_dir: Path, predictions: dict[str, dict]) -> None:
    path = data_dir / "incident-event-articles.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        raise ValueError(f"CSV has no header: {path}")

    updated = 0
    for row in rows:
        prediction = predictions.get(row["article_id"])
        if prediction is None:
            continue
        row["classifier_label"] = prediction["label"]
        row["classifier_score"] = str(prediction["score"])
        row["classifier_model"] = prediction["model"]
        updated += 1
    if updated != len(predictions):
        raise ValueError(f"Updated {updated} CSV rows for {len(predictions)} predictions")

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    texts, labels, evaluation = load_training_data(args.workbook)
    payload = load_dataset(args.data_dir)
    milk_incidents = [
        incident
        for incident in payload["incidents"]
        if incident.get("food_category") == "Milk"
    ]
    if not milk_incidents:
        raise ValueError("No published Milk incidents were found")
    if any(not incident.get("article_text") for incident in milk_incidents):
        raise ValueError("A published Milk incident has no article text")

    pipeline = build_pipeline()
    pipeline.fit(texts, labels)
    incident_texts = [
        full_text(incident.get("title", ""), incident["article_text"])
        for incident in milk_incidents
    ]
    predicted_labels = pipeline.predict(incident_texts).astype(int)
    probabilities = pipeline.predict_proba(incident_texts)[:, 1]

    predictions: dict[str, dict] = {}
    for incident, predicted, probability in zip(
        milk_incidents, predicted_labels, probabilities
    ):
        score = round(float(probability), 8)
        classifier = {
            "label": "relevant" if predicted == 1 else "irrelevant",
            "score": score,
            "model": MODEL_NAME,
            "prediction_date": args.prediction_date,
            "branch_scores": {},
        }
        incident["classifier"] = classifier
        predictions[incident["article_id"]] = classifier

    meta = payload["meta"]
    meta["classifier_scored_articles"] = sum(
        bool(incident.get("classifier")) for incident in payload["incidents"]
    )
    milk_release = meta.setdefault("milk_release", {})
    milk_release["classifier"] = {
        "model": MODEL_NAME,
        "training_articles": len(texts),
        "scored_articles": len(milk_incidents),
        "threshold": 0.5,
        "prediction_date": args.prediction_date,
        "evaluation": evaluation,
    }

    write_json(args.data_dir / "incident-events.json", payload)
    write_json(args.data_dir / "oil-events.json", payload)
    write_json(args.data_dir / "current-data-report.json", meta)
    update_article_csv(args.data_dir, predictions)

    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, args.model_output, compress=3)

    scores = [prediction["score"] for prediction in predictions.values()]
    audit = {
        "model": MODEL_NAME,
        "prediction_date": args.prediction_date,
        "training_workbook": str(args.workbook),
        "training_articles": len(texts),
        "training_label_counts": dict(Counter(map(int, labels))),
        "published_milk_articles_scored": len(predictions),
        "prediction_label_counts": dict(Counter(predicted_labels.tolist())),
        "score_min": min(scores),
        "score_max": max(scores),
        "score_mean": round(sum(scores) / len(scores), 8),
        "evaluation": evaluation,
        "runtime": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
    }
    write_json(args.audit_output, audit)
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
