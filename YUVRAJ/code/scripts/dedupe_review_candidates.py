from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.review_dedupe import load_reviewed_url_keys, split_new_review_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove URLs already human-reviewed in previous rounds from a review candidate CSV."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--excluded-output", type=Path, default=None)
    parser.add_argument("--summary-output", type=Path, default=None)
    parser.add_argument("--url-column", default="url")
    parser.add_argument("--master-dir", type=Path, default=ROOT / "reports" / "master_corpus")
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    rows, fieldnames = read_csv(args.input)
    if args.url_column not in fieldnames:
        raise ValueError(f"Missing URL column {args.url_column!r} in {args.input}")

    reviewed_keys = load_reviewed_url_keys(master_dir=args.master_dir, reports_dir=args.reports_dir)
    new_rows, excluded_rows = split_new_review_rows(rows, reviewed_keys, url_column=args.url_column)

    write_csv(args.output, new_rows, fieldnames)
    excluded_output = args.excluded_output or args.output.with_name(args.output.stem + "_already_reviewed.csv")
    write_csv(excluded_output, excluded_rows, fieldnames)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "output": str(args.output),
        "excluded_output": str(excluded_output),
        "url_column": args.url_column,
        "reviewed_url_key_count": len(reviewed_keys),
        "input_rows": len(rows),
        "new_review_rows": len(new_rows),
        "already_reviewed_rows_removed": len(excluded_rows),
    }
    summary_output = args.summary_output or args.output.with_name(args.output.stem + "_dedupe_summary.json")
    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
