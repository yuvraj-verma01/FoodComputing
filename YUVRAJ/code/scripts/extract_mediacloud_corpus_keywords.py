"""Extract keyword candidates from the crawled Media Cloud article corpus.

This reads article text already stored in the crawler database. It does not
download URLs or call Media Cloud.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from crawl_sample_keywords import (  # noqa: E402
    COMPOSITE_WEIGHTS,
    METHODS,
    extract_keyword_candidates,
    write_corpus,
    write_csv,
    write_jsonl,
)


DEFAULT_RUN_DIR = ROOT / "data" / "runs" / "edible_oils_from_sample_2026-06-21"
DEFAULT_DB = DEFAULT_RUN_DIR / "mediacloud" / "outputs" / "articles.db"
DEFAULT_OUTPUT_DIR = DEFAULT_RUN_DIR / "mediacloud" / "outputs"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--include-duplicates",
        action="store_true",
        help="Include articles marked as duplicates in keyword scoring.",
    )
    parser.add_argument(
        "--relevance-scope",
        choices=["all", "relevant"],
        default="all",
        help="Use all extracted articles or only articles labelled relevant.",
    )
    args = parser.parse_args()

    rows = load_article_rows(args.db)
    source_rows = select_keyword_source_rows(
        rows,
        include_duplicates=args.include_duplicates,
        relevance_scope=args.relevance_scope,
    )
    docs = rows_to_docs(source_rows)

    candidates = only_literal_candidates(extract_keyword_candidates(docs))
    add_example_metadata(candidates, docs)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    corpus_articles_csv = args.output_dir / "mediacloud_corpus_articles.csv"
    corpus_articles_jsonl = args.output_dir / "mediacloud_corpus_articles.jsonl"
    corpus_txt = args.output_dir / "mediacloud_corpus.txt"
    keyword_csv = args.output_dir / "mediacloud_keyword_candidates_clean.csv"
    keyword_jsonl = args.output_dir / "mediacloud_keyword_candidates_clean.jsonl"
    summary_json = args.output_dir / "mediacloud_keyword_summary.json"

    write_csv(corpus_articles_csv, article_manifest_rows(rows))
    write_jsonl(corpus_articles_jsonl, article_manifest_rows(rows))
    write_corpus(corpus_txt, docs)
    write_csv(keyword_csv, candidates)
    write_jsonl(keyword_jsonl, candidates)

    summary = build_summary(
        db_path=args.db,
        output_dir=args.output_dir,
        rows=rows,
        source_rows=source_rows,
        candidates=candidates,
        include_duplicates=args.include_duplicates,
        relevance_scope=args.relevance_scope,
        outputs={
            "corpus_articles_csv": str(corpus_articles_csv),
            "corpus_articles_jsonl": str(corpus_articles_jsonl),
            "corpus_text": str(corpus_txt),
            "keyword_candidates_csv": str(keyword_csv),
            "keyword_candidates_jsonl": str(keyword_jsonl),
        },
    )
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def load_article_rows(db_path: Path) -> list[dict]:
    if not db_path.exists():
        raise FileNotFoundError(f"Missing article database: {db_path}")
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            select article_id, title, url, canonical_url, source, domain,
                   publication_date, discovered_at, crawled_at, query_used,
                   discovery_method, cleaned_text_path, article_text,
                   extraction_status, word_count, relevance_score,
                   relevance_label, is_duplicate, duplicate_of_url,
                   error_message
            from articles
            order by publication_date desc nulls last, rowid asc
            """
        ).fetchall()
    return [dict(row) for row in rows]


def select_keyword_source_rows(
    rows: list[dict],
    *,
    include_duplicates: bool,
    relevance_scope: str,
) -> list[dict]:
    selected = []
    for row in rows:
        text = (row.get("article_text") or "").strip()
        if not text:
            continue
        if not include_duplicates and int(row.get("is_duplicate") or 0):
            continue
        if relevance_scope == "relevant" and row.get("relevance_label") != "relevant":
            continue
        selected.append(row)
    return selected


def rows_to_docs(rows: list[dict]) -> list[dict]:
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
                "publication_date": row.get("publication_date") or "",
                "query_used": row.get("query_used") or "",
                "relevance_label": row.get("relevance_label") or "",
                "relevance_score": row.get("relevance_score") or "",
                "word_count": row.get("word_count") or "",
                "text": row.get("article_text") or "",
            }
        )
    return docs


def add_example_metadata(candidates: list[dict], docs: list[dict]) -> None:
    docs_by_number = {doc["article_number"]: doc for doc in docs}
    for candidate in candidates:
        doc = docs_by_number.get(candidate.get("example_article_number"))
        if not doc:
            candidate.update(
                {
                    "example_article_id": "",
                    "example_domain": "",
                    "example_publication_date": "",
                    "example_relevance_label": "",
                    "example_relevance_score": "",
                    "example_query_used": "",
                    "example_word_count": "",
                }
            )
            continue
        candidate.update(
            {
                "example_article_id": doc.get("article_id") or "",
                "example_domain": doc.get("domain") or "",
                "example_publication_date": doc.get("publication_date") or "",
                "example_relevance_label": doc.get("relevance_label") or "",
                "example_relevance_score": doc.get("relevance_score") or "",
                "example_query_used": doc.get("query_used") or "",
                "example_word_count": doc.get("word_count") or "",
            }
        )


def only_literal_candidates(candidates: list[dict]) -> list[dict]:
    """Keep candidates that were found as exact phrases in the corpus text."""
    return [
        row
        for row in candidates
        if int(row.get("total_frequency") or 0) > 0
        and int(row.get("document_frequency") or 0) > 0
    ]


def article_manifest_rows(rows: list[dict]) -> list[dict]:
    fields = [
        "article_id",
        "title",
        "url",
        "source",
        "domain",
        "publication_date",
        "query_used",
        "discovery_method",
        "extraction_status",
        "word_count",
        "relevance_score",
        "relevance_label",
        "is_duplicate",
        "duplicate_of_url",
        "cleaned_text_path",
        "error_message",
    ]
    return [{field: row.get(field) or "" for field in fields} for row in rows]


def build_summary(
    *,
    db_path: Path,
    output_dir: Path,
    rows: list[dict],
    source_rows: list[dict],
    candidates: list[dict],
    include_duplicates: bool,
    relevance_scope: str,
    outputs: dict[str, str],
) -> dict:
    extracted_rows = [row for row in rows if (row.get("article_text") or "").strip()]
    label_counts = Counter(row.get("relevance_label") or "" for row in rows)
    extraction_counts = Counter(row.get("extraction_status") or "" for row in rows)
    candidate_label_counts = Counter(row.get("review_label") or "" for row in candidates)
    category_counts = Counter(row.get("category") or "" for row in candidates)
    duplicate_count = sum(int(row.get("is_duplicate") or 0) for row in rows)
    word_counts = [
        int(row.get("word_count") or 0)
        for row in source_rows
        if int(row.get("word_count") or 0) > 0
    ]

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "output_dir": str(output_dir),
        "article_rows_total": len(rows),
        "article_rows_with_text": len(extracted_rows),
        "keyword_source_articles": len(source_rows),
        "include_duplicates_for_keywords": include_duplicates,
        "relevance_scope_for_keywords": relevance_scope,
        "duplicates_marked_in_db": duplicate_count,
        "extraction_status_counts": dict(sorted(extraction_counts.items())),
        "relevance_label_counts": dict(sorted(label_counts.items())),
        "keyword_source_word_count_min": min(word_counts) if word_counts else 0,
        "keyword_source_word_count_max": max(word_counts) if word_counts else 0,
        "keyword_source_word_count_avg": round(sum(word_counts) / len(word_counts), 1)
        if word_counts
        else 0,
        "keyword_candidates_clean": len(candidates),
        "candidate_review_label_counts": dict(sorted(candidate_label_counts.items())),
        "candidate_category_counts": dict(sorted(category_counts.items())),
        "scoring": {
            "candidate_creation_methods": list(METHODS),
            "reference_lexicon_use": "categorization_only",
            "composite_weights": COMPOSITE_WEIGHTS,
            "review_labels": ["keep_core", "manual_review", "drop"],
            "note": "Counts are deterministic; label thresholds are heuristic triage for review.",
            "literal_phrase_filter": "Candidates with zero exact phrase frequency are removed.",
        },
        "outputs": outputs,
    }


if __name__ == "__main__":
    raise SystemExit(main())
