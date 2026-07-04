from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from crawl_sample_keywords import (  # noqa: E402
    COMPOSITE_WEIGHTS,
    METHODS,
    extract_keyword_candidates,
    write_csv,
    write_jsonl,
)


DEFAULT_SOURCE = ROOT / Path(
    "data/runs/edible_oil_adulteration_round_02_2026-06-23/"
    "mediacloud/outputs/oil_relevance/metadata_rescue_fulltext_added.csv"
)
DEFAULT_OUTPUT_DIR = ROOT / "reports" / "edible_oil_adulteration_round_02" / "round_03_keyword_review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Round 3 keyword candidates only from newly appended Round 2 rescue articles."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-round-number", default="2")
    parser.add_argument("--next-round-target", default="3")
    parser.add_argument("--top", type=int, default=0)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def load_prior_keywords() -> dict[str, str]:
    prior: dict[str, str] = {}
    patterns = [
        "reports/edible_oil_adulteration_round_*/keyword_review/*keyword*.csv",
        "reports/edible_oil_adulteration_round_*/not_terms_review/*keyword*.csv",
        "reports/edible_oil_adulteration_round_*/not_terms_review/*not_terms*.csv",
        "reports/edible_oil_adulteration_round_*/keyword_review/*bank*.csv",
    ]
    for pattern in patterns:
        for path in sorted(ROOT.glob(pattern)):
            for row in read_csv(path):
                term = (
                    row.get("keyword_or_keyphrase")
                    or row.get("term")
                    or row.get("keyword")
                    or ""
                ).strip()
                if not term:
                    continue
                prior.setdefault(normalize_keyword(term), str(path.relative_to(ROOT)))
    return prior


def add_metadata(
    candidates: list[dict[str, Any]],
    docs: list[dict[str, Any]],
    source_round_number: str,
    next_round_target: str,
) -> None:
    docs_by_number = {doc["article_number"]: doc for doc in docs}
    for row in candidates:
        doc = docs_by_number.get(row.get("example_article_number"))
        row.update(
            {
                "source_round_number": source_round_number,
                "next_round_target": next_round_target,
                "keyword_source_scope": "new_unique_round_02_rescue_relevant_articles_only",
                "keyword_source_article_count": len(docs),
                "example_article_id": doc.get("article_id", "") if doc else "",
                "example_domain": doc.get("domain", "") if doc else "",
                "example_source": doc.get("source", "") if doc else "",
                "example_publication_date": doc.get("publication_date", "") if doc else "",
                "example_human_label": doc.get("relevance_label", "") if doc else "",
                "example_word_count": doc.get("word_count", "") if doc else "",
            }
        )


def split_prior_seen(candidates: list[dict[str, Any]], prior: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    new_rows: list[dict[str, Any]] = []
    seen_rows: list[dict[str, Any]] = []
    seen_this_output: set[str] = set()
    for row in candidates:
        term = row.get("keyword_or_keyphrase") or ""
        norm = normalize_keyword(str(term))
        if norm in prior:
            seen_rows.append({**row, "prior_keyword_match_file": prior[norm], "normalized_keyword": norm})
            continue
        if norm in seen_this_output:
            seen_rows.append({**row, "prior_keyword_match_file": "duplicate_within_round3_output", "normalized_keyword": norm})
            continue
        row["normalized_keyword"] = norm
        new_rows.append(row)
        seen_this_output.add(norm)
    return new_rows, seen_rows


def write_corpus(path: Path, docs: list[dict[str, Any]]) -> None:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(("\n\n" + "=" * 80 + "\n\n").join(chunks), encoding="utf-8")


def main() -> int:
    args = parse_args()
    source_rows = [
        row
        for row in read_csv(args.source)
        if row.get("final_keep") == "1" and (row.get("article_text") or "").strip()
    ]
    docs = rows_to_docs(source_rows)
    candidates = only_literal_candidates(extract_keyword_candidates(docs))
    add_metadata(candidates, docs, args.source_round_number, args.next_round_target)
    prior_keywords = load_prior_keywords()
    new_candidates, prior_seen = split_prior_seen(candidates, prior_keywords)
    if args.top:
        new_candidates = new_candidates[: args.top]

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    prefix = "round_03_from_round_02_rescue"
    keyword_csv = out / f"{prefix}_keyword_candidates.csv"
    keyword_jsonl = out / f"{prefix}_keyword_candidates.jsonl"
    prior_seen_csv = out / f"{prefix}_already_seen_keywords.csv"
    source_csv = out / f"{prefix}_source_articles.csv"
    corpus_txt = out / f"{prefix}_corpus.txt"
    summary_json = out / f"{prefix}_keyword_extraction_summary.json"

    write_csv(keyword_csv, new_candidates)
    write_jsonl(keyword_jsonl, new_candidates)
    write_csv(prior_seen_csv, prior_seen)
    write_corpus(corpus_txt, docs)
    write_csv(
        source_csv,
        [
            {
                "source_round_number": args.source_round_number,
                "next_round_target": args.next_round_target,
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
        "source_file": str(args.source),
        "source_scope": "new unique Round 2 metadata-rescue relevant articles only",
        "source_round_number": args.source_round_number,
        "next_round_target": args.next_round_target,
        "source_articles": len(source_rows),
        "source_articles_with_text": len(docs),
        "raw_keyword_candidates_before_prior_filter": len(candidates),
        "prior_keyword_normalized_count": len(prior_keywords),
        "already_seen_keyword_candidates_removed": len(prior_seen),
        "new_keyword_candidates": len(new_candidates),
        "candidate_review_label_counts": dict(Counter(row.get("review_label", "") for row in new_candidates)),
        "candidate_category_counts": dict(Counter(row.get("category", "") for row in new_candidates)),
        "scoring": {
            "candidate_creation_methods": list(METHODS),
            "composite_weights": COMPOSITE_WEIGHTS,
            "review_labels": ["keep_core", "manual_review", "drop"],
            "note": "Keyword extraction is heuristic. Exact normalized prior keywords from earlier review/final files were removed.",
        },
        "outputs": {
            "keyword_candidates_csv": str(keyword_csv),
            "keyword_candidates_jsonl": str(keyword_jsonl),
            "already_seen_keywords_csv": str(prior_seen_csv),
            "source_articles_csv": str(source_csv),
            "corpus_text": str(corpus_txt),
            "keyword_review_workbook": str(out / f"{prefix}_keyword_review.xlsx"),
        },
    }
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
