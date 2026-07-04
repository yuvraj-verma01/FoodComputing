from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from shutil import copyfile


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = ROOT / "data" / "runs" / "ghee_from_sample_2026-06-30"
DEFAULT_REPORT_DIR = ROOT / "reports" / "ghee_keyword_review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a literal-only ghee keyword review CSV for URL discovery."
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
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


def literal_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    seen: set[str] = set()
    for row in rows:
        term = (row.get("keyword_or_keyphrase") or "").strip()
        if not term:
            continue
        if int(row.get("total_frequency") or 0) <= 0:
            continue
        if int(row.get("document_frequency") or 0) <= 0:
            continue
        norm = " ".join(term.lower().split())
        if norm in seen:
            continue
        seen.add(norm)
        out.append(row)
    return out


def main() -> int:
    args = parse_args()
    source_csv = args.run_dir / "sample_keyword_candidates_clean.csv"
    source_articles = args.run_dir / "sample_articles.csv"
    source_summary = args.run_dir / "sample_keyword_clean_summary.json"
    source_urls = args.run_dir / "source_urls_from_docx.csv"
    if not source_csv.exists():
        raise FileNotFoundError(f"Missing keyword candidate CSV: {source_csv}")

    raw_rows = read_csv(source_csv)
    rows = literal_rows(raw_rows)
    args.report_dir.mkdir(parents=True, exist_ok=True)

    review_csv = args.report_dir / "ghee_sample_keyword_candidates_for_review.csv"
    article_csv = args.report_dir / "ghee_sample_article_status.csv"
    summary_json = args.report_dir / "ghee_sample_keyword_review_summary.json"
    write_csv(review_csv, rows)
    if source_articles.exists():
        copyfile(source_articles, article_csv)

    source_summary_data = {}
    if source_summary.exists():
        source_summary_data = json.loads(source_summary.read_text(encoding="utf-8"))
    article_rows = read_csv(source_articles) if source_articles.exists() else []
    url_count = source_summary_data.get("urls_from_docx", "")
    if not url_count and source_urls.exists():
        url_count = len(read_csv(source_urls))
    download_success = source_summary_data.get("download_success", "")
    extraction_success = source_summary_data.get("extraction_success_or_partial", "")
    if article_rows:
        download_success = sum(
            1
            for row in article_rows
            if row.get("download_status") in {"success", "success_reader_fallback"}
        )
        extraction_success = sum(
            1
            for row in article_rows
            if row.get("extraction_status") in {"success", "partial"}
        )

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(args.run_dir),
        "report_dir": str(args.report_dir),
        "source_docx": source_summary_data.get("docx", ""),
        "urls_from_docx": url_count,
        "download_success_or_reader_fallback": download_success,
        "extraction_success_or_partial": extraction_success,
        "keyword_source_articles": source_summary_data.get("keyword_source_articles", ""),
        "raw_keyword_candidates": len(raw_rows),
        "literal_keyword_candidates_for_review": len(rows),
        "review_label_counts": dict(Counter(row.get("review_label", "") for row in rows)),
        "category_counts": dict(Counter(row.get("category", "") for row in rows)),
        "note": (
            "Review CSV excludes TF-IDF/YAKE candidates with zero exact phrase frequency. "
            "Rows still include the extractor's keep_core/manual_review/drop suggestion; "
            "the human keep column in the Excel workbook is the authority."
        ),
        "outputs": {
            "review_csv": str(review_csv),
            "review_workbook": str(args.report_dir / "ghee_sample_keyword_review.xlsx"),
            "article_status_csv": str(article_csv),
            "raw_candidate_csv": str(source_csv),
        },
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
