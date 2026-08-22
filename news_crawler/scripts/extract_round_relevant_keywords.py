from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from crawl_sample_keywords import (  # noqa: E402
    COMPOSITE_WEIGHTS,
    METHODS,
    extract_keyword_candidates,
    write_csv,
    write_jsonl,
)


DEFAULT_ROUND_REPORT = ROOT / "reports" / "edible_oil_adulteration_round_01"
DEFAULT_OUTPUT_DIR = DEFAULT_ROUND_REPORT / "keyword_review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract keyword candidates from human-reviewed articles for the next round."
    )
    parser.add_argument("--round-report", type=Path, default=DEFAULT_ROUND_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--round-number", default="1")
    parser.add_argument(
        "--label",
        choices=["relevant", "irrelevant"],
        default="relevant",
        help="Extract from this human-reviewed label subset.",
    )
    parser.add_argument("--top", type=int, default=0, help="Optional top-N candidates to keep after sorting.")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def rows_to_docs(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    docs = []
    for index, row in enumerate(rows, start=1):
        docs.append(
            {
                "article_number": index,
                "article_id": row.get("article_id") or "",
                "title": row.get("title") or f"Article {index}",
                "url": row.get("url") or "",
                "domain": row.get("domain") or "",
                "source": row.get("source") or "",
                "publication_date": row.get("publication_date") or row.get("date") or "",
                "query_used": row.get("query_id") or "",
                "relevance_label": row.get("final_human_label") or "",
                "relevance_score": row.get("model_confidence") or "",
                "word_count": row.get("word_count") or "",
                "text": row.get("article_text") or "",
            }
        )
    return docs


def only_literal_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in candidates
        if int(row.get("total_frequency") or 0) > 0
        and int(row.get("document_frequency") or 0) > 0
    ]


def add_round_metadata(
    candidates: list[dict[str, Any]],
    docs: list[dict[str, Any]],
    round_number: str,
    label: str,
) -> None:
    docs_by_number = {doc["article_number"]: doc for doc in docs}
    for row in candidates:
        doc = docs_by_number.get(row.get("example_article_number"))
        row.update(
            {
                "source_round_number": round_number,
                "next_round_target": str(int(round_number) + 1) if round_number.isdigit() else "",
                "keyword_source_scope": f"human_{label}_articles_only",
                "keyword_source_article_count": len(docs),
                "example_article_id": doc.get("article_id", "") if doc else "",
                "example_domain": doc.get("domain", "") if doc else "",
                "example_source": doc.get("source", "") if doc else "",
                "example_publication_date": doc.get("publication_date", "") if doc else "",
                "example_human_label": doc.get("relevance_label", "") if doc else "",
                "example_word_count": doc.get("word_count", "") if doc else "",
            }
        )


def write_corpus(path: Path, docs: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    chunks = []
    for doc in docs:
        chunks.append(
            "\n".join(
                [
                    f"ARTICLE {doc['article_number']}",
                    f"TITLE: {doc.get('title', '')}",
                    f"URL: {doc.get('url', '')}",
                    "",
                    doc.get("text", ""),
                ]
            )
        )
    path.write_text("\n\n" + ("=" * 80) + "\n\n".join(chunks), encoding="utf-8")


def main() -> None:
    args = parse_args()
    label = args.label
    prefix = f"round_{int(args.round_number):02d}_{label}"
    input_path = args.round_report / f"{prefix}_articles.csv"
    rows = read_csv(input_path)
    text_rows = [row for row in rows if (row.get("article_text") or "").strip()]
    docs = rows_to_docs(text_rows)
    candidates = only_literal_candidates(extract_keyword_candidates(docs))
    add_round_metadata(candidates, docs, args.round_number, label)
    if args.top:
        candidates = candidates[: args.top]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    keyword_csv = args.output_dir / f"{prefix}_keyword_candidates.csv"
    keyword_jsonl = args.output_dir / f"{prefix}_keyword_candidates.jsonl"
    corpus_txt = args.output_dir / f"{prefix}_corpus.txt"
    manifest_csv = args.output_dir / f"{prefix}_keyword_source_articles.csv"
    summary_json = args.output_dir / f"{prefix}_keyword_extraction_summary.json"

    write_csv(keyword_csv, candidates)
    write_jsonl(keyword_jsonl, candidates)
    write_corpus(corpus_txt, docs)
    write_csv(
        manifest_csv,
        [
            {
                "source_round_number": args.round_number,
                "source_human_label": label,
                "article_number": doc["article_number"],
                "article_id": doc.get("article_id", ""),
                "title": doc.get("title", ""),
                "source": doc.get("source", ""),
                "domain": doc.get("domain", ""),
                "publication_date": doc.get("publication_date", ""),
                "url": doc.get("url", ""),
                "word_count": doc.get("word_count", ""),
            }
            for doc in docs
        ],
    )

    summary = {
        "created_at": utc_now(),
        "source_round_number": args.round_number,
        "next_round_target": str(int(args.round_number) + 1) if args.round_number.isdigit() else "",
        "source_human_label": label,
        "source_article_file": str(input_path),
        "source_articles": len(rows),
        "source_articles_with_text": len(docs),
        "keyword_candidates": len(candidates),
        "candidate_review_label_counts": dict(Counter(row.get("review_label", "") for row in candidates)),
        "candidate_category_counts": dict(Counter(row.get("category", "") for row in candidates)),
        "scoring": {
            "candidate_creation_methods": list(METHODS),
            "composite_weights": COMPOSITE_WEIGHTS,
            "review_labels": ["keep_core", "manual_review", "drop"],
            "note": "Keyword extraction is a heuristic review aid. Your keep column is authoritative.",
        },
        "outputs": {
            "keyword_candidates_csv": str(keyword_csv),
            "keyword_candidates_jsonl": str(keyword_jsonl),
            "keyword_review_workbook": str(args.output_dir / f"{prefix}_keyword_review.xlsx"),
            "source_articles_csv": str(manifest_csv),
            "corpus_text": str(corpus_txt),
        },
    }
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
