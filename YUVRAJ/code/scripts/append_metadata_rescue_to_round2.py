from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.oil_relevance import classify_oil_relevance, merge_rule_and_llm, ollama_relevance_check
from crawler.review_dedupe import normalized_url


DEFAULT_OUTPUT_DIR = ROOT / Path(
    "data/runs/edible_oil_adulteration_round_02_2026-06-23/"
    "mediacloud/outputs/oil_relevance"
)
DEFAULT_DB = ROOT / Path(
    "data/runs/edible_oil_adulteration_round_02_2026-06-23/"
    "mediacloud/outputs/articles.db"
)
DEFAULT_QUEUE = DEFAULT_OUTPUT_DIR / "metadata_reject_llm_human_crawl_queue.csv"
DEFAULT_CRAWL_LOG = DEFAULT_OUTPUT_DIR / "metadata_rescue_crawl_log.csv"

FINAL_COLUMNS = [
    "final_keep",
    "final_human_label",
    "human_review_status",
    "human_review_source",
    "model_final_label",
    "model_confidence",
    "title",
    "source",
    "date",
    "url",
    "domain",
    "publication_date",
    "word_count",
    "reason",
    "evidence_phrase",
    "llm_label",
    "llm_confidence",
    "llm_reason",
    "oil_role",
    "edible_oil_terms",
    "adulteration_action_terms",
    "negative_terms",
    "query_family",
    "query_id",
    "article_id",
    "file_path",
    "cleaned_text_path",
    "article_text",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append full-text classified metadata-rescue articles into Round 2 final outputs."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--crawl-log", type=Path, default=DEFAULT_CRAWL_LOG)
    parser.add_argument("--llm-model", default="llama3.1:8b-instruct-q4_K_M")
    parser.add_argument("--skip-llm", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_articles(db_path: Path, urls: list[str]) -> dict[str, dict[str, Any]]:
    if not urls:
        return {}
    placeholders = ",".join("?" for _ in urls)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(f"SELECT * FROM articles WHERE url IN ({placeholders})", urls).fetchall()
    return {row["url"]: dict(row) for row in rows}


def load_done_llm(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    out = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("url"):
                out[row["url"]] = row
    return out


def append_llm_result(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def classify_article(
    article: dict[str, Any],
    queue_row: dict[str, str],
    llm_by_url: dict[str, dict[str, Any]],
    llm_path: Path,
    model: str,
    skip_llm: bool,
) -> dict[str, Any]:
    url = article.get("url") or queue_row.get("url") or ""
    title = article.get("title") or queue_row.get("title") or ""
    text = article.get("article_text") or ""
    rule = classify_oil_relevance(title=title, text=text, url=url)
    llm = llm_by_url.get(url)
    if not skip_llm and not llm:
        try:
            llm = ollama_relevance_check(title=title, text=text, url=url, model=model, timeout_seconds=240)
        except Exception as exc:
            llm = {
                "llm_label": "unclear",
                "llm_confidence": 0.0,
                "llm_reason": f"LLM call failed: {exc}",
                "evidence_phrase": "",
                "llm_model": model,
            }
        append_llm_result(llm_path, {"url": url, **llm})
        llm_by_url[url] = llm
    merged = merge_rule_and_llm(rule, llm)
    final_label = merged.get("final_label") or "irrelevant"
    keep = "1" if final_label == "relevant" else "0"
    return {
        "final_keep": keep,
        "final_human_label": "relevant" if keep == "1" else "irrelevant",
        "human_review_status": "metadata_rescue_fulltext_classified",
        "human_review_source": "metadata_reject_llm_review.xlsx:Review; metadata_rescue_fulltext_rules_ollama",
        "model_final_label": final_label,
        "model_confidence": merged.get("confidence", ""),
        "title": title,
        "source": article.get("source") or queue_row.get("source") or "",
        "date": article.get("publication_date") or queue_row.get("date") or "",
        "url": url,
        "domain": article.get("domain") or "",
        "publication_date": article.get("publication_date") or queue_row.get("date") or "",
        "word_count": article.get("word_count") or "",
        "reason": merged.get("reason", ""),
        "evidence_phrase": merged.get("evidence_phrase", ""),
        "llm_label": merged.get("llm_label", ""),
        "llm_confidence": merged.get("llm_confidence", ""),
        "llm_reason": merged.get("llm_reason", ""),
        "oil_role": merged.get("oil_role", ""),
        "edible_oil_terms": merged.get("edible_oil_terms", ""),
        "adulteration_action_terms": merged.get("adulteration_action_terms", ""),
        "negative_terms": merged.get("negative_terms", ""),
        "query_family": queue_row.get("query_family", ""),
        "query_id": queue_row.get("query_id", ""),
        "article_id": article.get("article_id") or "",
        "file_path": article.get("cleaned_text_path") or article.get("raw_html_path") or "",
        "cleaned_text_path": article.get("cleaned_text_path") or "",
        "article_text": text,
    }


def write_final_outputs(output_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    relevant = [row for row in rows if row.get("final_keep") == "1"]
    irrelevant = [row for row in rows if row.get("final_keep") == "0"]
    unresolved = [row for row in rows if row.get("final_keep") not in {"0", "1"}]
    write_csv(output_dir / "final_human_reviewed_all_articles.csv", rows, FINAL_COLUMNS)
    write_csv(output_dir / "final_relevant_articles.csv", relevant, FINAL_COLUMNS)
    write_csv(output_dir / "final_irrelevant_articles.csv", irrelevant, FINAL_COLUMNS)
    write_csv(output_dir / "final_unresolved_articles.csv", unresolved, FINAL_COLUMNS)
    write_jsonl(output_dir / "final_relevant_articles.jsonl", relevant)
    (output_dir / "final_review_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    final_path = output_dir / "final_human_reviewed_all_articles.csv"
    existing_rows = read_csv(final_path)
    existing_keys = {normalized_url(row.get("url", "")) for row in existing_rows if row.get("url")}

    queue_rows = [row for row in read_csv(args.queue) if row.get("url")]
    crawl_log = {row.get("url", ""): row for row in read_csv(args.crawl_log)}
    urls = [row["url"] for row in queue_rows]
    articles = load_articles(args.db, urls)
    llm_path = output_dir / "metadata_rescue_fulltext_llm_results.jsonl"
    llm_by_url = load_done_llm(llm_path)

    classified_rows: list[dict[str, Any]] = []
    not_added_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    for row in queue_rows:
        url = row["url"]
        article = articles.get(url)
        log = crawl_log.get(url, {})
        if normalized_url(url) in existing_keys:
            duplicate_rows.append({**row, "not_added_reason": "already_in_round2_final_outputs"})
            continue
        if not article or not (article.get("article_text") or "").strip():
            not_added_rows.append(
                {
                    **row,
                    "crawl_status": log.get("status", ""),
                    "http_status": log.get("http_status", ""),
                    "not_added_reason": "no_extracted_article_text",
                    "error_message": log.get("error_message", ""),
                }
            )
            continue
        classified_rows.append(
            classify_article(
                article=article,
                queue_row=row,
                llm_by_url=llm_by_url,
                llm_path=llm_path,
                model=args.llm_model,
                skip_llm=args.skip_llm,
            )
        )

    added_rows = [row for row in classified_rows if normalized_url(row.get("url", "")) not in existing_keys]
    final_rows = existing_rows + added_rows
    label_counts = Counter(row.get("final_human_label", "") for row in final_rows)
    rescue_label_counts = Counter(row.get("final_human_label", "") for row in added_rows)
    summary = {
        "created_at": utc_now(),
        "source_workbook": str(output_dir / "human_reviewed_corpus.xlsx"),
        "rescue_append_source": str(args.queue),
        "total_rows": len(final_rows),
        "original_rows_before_rescue_append": len(existing_rows),
        "rescue_queue_rows": len(queue_rows),
        "rescue_articles_with_text_classified": len(classified_rows),
        "rescue_rows_added": len(added_rows),
        "rescue_rows_not_added_no_text": len(not_added_rows),
        "rescue_duplicate_rows_skipped": len(duplicate_rows),
        "rescue_added_label_counts": dict(sorted(rescue_label_counts.items())),
        "final_label_counts": dict(sorted(label_counts.items())),
        "final_relevant_with_article_text": sum(
            1 for row in final_rows if row.get("final_keep") == "1" and (row.get("article_text") or "").strip()
        ),
        "unresolved_rows": sum(1 for row in final_rows if row.get("final_keep") not in {"0", "1"}),
    }

    write_csv(output_dir / "metadata_rescue_fulltext_classified.csv", classified_rows, FINAL_COLUMNS)
    write_csv(output_dir / "metadata_rescue_fulltext_added.csv", added_rows, FINAL_COLUMNS)
    write_csv(
        output_dir / "metadata_rescue_fulltext_not_added.csv",
        not_added_rows + duplicate_rows,
        list((not_added_rows + duplicate_rows)[0].keys()) if (not_added_rows + duplicate_rows) else ["url", "not_added_reason"],
    )
    write_final_outputs(output_dir, final_rows, summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Added rows written: {(output_dir / 'metadata_rescue_fulltext_added.csv').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
