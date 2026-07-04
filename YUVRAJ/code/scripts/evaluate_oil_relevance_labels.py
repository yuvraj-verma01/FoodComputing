"""Evaluate manual validation labels for the oil relevance pipeline."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLE = (
    ROOT
    / "data"
    / "runs"
    / "edible_oils_boolean_title_proximity_2026-06-22"
    / "mediacloud"
    / "outputs"
    / "oil_relevance"
    / "manual_validation_sample.csv"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    rows = read_rows(args.input)
    labelled = [
        row for row in rows
        if (row.get("manual_label") or "").strip().lower() in {"relevant", "irrelevant"}
    ]
    if not labelled:
        raise SystemExit("No rows with manual_label=relevant/irrelevant found.")

    counts = Counter()
    false_positives = []
    false_negatives = []
    for row in labelled:
        predicted = normalize_pred(row.get("final_label") or "")
        manual = (row.get("manual_label") or "").strip().lower()
        if predicted == "relevant" and manual == "relevant":
            counts["tp"] += 1
        elif predicted == "relevant" and manual == "irrelevant":
            counts["fp"] += 1
            false_positives.append(row)
        elif predicted == "irrelevant" and manual == "relevant":
            counts["fn"] += 1
            false_negatives.append(row)
        else:
            counts["tn"] += 1

    precision = safe_div(counts["tp"], counts["tp"] + counts["fp"])
    recall = safe_div(counts["tp"], counts["tp"] + counts["fn"])
    f1 = safe_div(2 * precision * recall, precision + recall)
    report = {
        "input": str(args.input),
        "labelled_rows": len(labelled),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": {
            "true_positive": counts["tp"],
            "false_positive": counts["fp"],
            "false_negative": counts["fn"],
            "true_negative": counts["tn"],
        },
        "false_positive_urls": [row.get("url") for row in false_positives],
        "false_negative_urls": [row.get("url") for row in false_negatives],
    }

    output = args.output or args.input.with_name("manual_validation_metrics.json")
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_pred(label: str) -> str:
    label = label.strip().lower()
    return "relevant" if label == "relevant" else "irrelevant"


def safe_div(num: float, den: float) -> float:
    return round(num / den, 4) if den else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
