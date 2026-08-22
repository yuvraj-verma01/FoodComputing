"""Run staged relevance filtering for edible-oil adulteration articles.

Stages:
  metadata  - classify all discovered URL records using title/URL/query metadata
  crawl     - crawl/extract candidate URLs selected by metadata stage
  rules     - classify extracted article text with deterministic role rules
  llm       - ask local Ollama to read extracted rule candidates
  outputs   - merge rule/LLM decisions into final CSVs and summary
  all       - metadata, crawl, rules, llm, outputs
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.config import Config
from crawler.downloader import Downloader
from crawler.extractor import Extractor
from crawler.oil_relevance import (
    classify_oil_relevance,
    merge_rule_and_llm,
    ollama_relevance_check,
)
from crawler.review_dedupe import load_reviewed_url_keys, split_new_review_rows
from crawler.storage import Storage


DEFAULT_RUN_DIR = ROOT / "data" / "runs" / "edible_oil_adulteration_round_02_2026-06-23"
DEFAULT_CONFIG = ROOT / "config" / "config_edible_oils_combined.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--stage",
        choices=["metadata", "crawl", "rules", "llm", "outputs", "all"],
        default="metadata",
    )
    parser.add_argument("--crawl-limit", type=int, default=0, help="0 means no limit.")
    parser.add_argument("--llm-limit", type=int, default=0, help="0 means no limit.")
    parser.add_argument(
        "--llm-model",
        default="llama3.1:8b-instruct-q4_K_M",
        help="Local Ollama model name.",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="For stage=all, skip Ollama and produce rule-only outputs.",
    )
    parser.add_argument(
        "--include-reviewed-urls",
        action="store_true",
        help="Do not exclude URLs already human-marked in previous round/master outputs.",
    )
    args = parser.parse_args()

    setup_logging()
    cfg = Config(args.config)
    output_dir = relevance_dir(args.run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stages = expand_stages(args.stage, skip_llm=args.skip_llm)
    if "metadata" in stages:
        run_metadata_stage(cfg, output_dir, include_reviewed_urls=args.include_reviewed_urls)
    if "crawl" in stages:
        run_crawl_stage(cfg, output_dir, limit=args.crawl_limit)
    if "rules" in stages:
        run_rules_stage(cfg, output_dir)
    if "llm" in stages:
        run_llm_stage(cfg, output_dir, model=args.llm_model, limit=args.llm_limit)
    if "outputs" in stages:
        run_outputs_stage(cfg, output_dir)

    print(f"Oil relevance outputs: {output_dir}")
    return 0


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def expand_stages(stage: str, skip_llm: bool) -> list[str]:
    if stage == "all":
        stages = ["metadata", "crawl", "rules"]
        if not skip_llm:
            stages.append("llm")
        stages.append("outputs")
        return stages
    return [stage]


def relevance_dir(run_dir: Path) -> Path:
    return run_dir / "mediacloud" / "outputs" / "oil_relevance"


def run_metadata_stage(cfg: Config, output_dir: Path, include_reviewed_urls: bool = False) -> None:
    db_path = cfg.path("db")
    records = read_discovered(db_path)
    previously_reviewed: list[dict[str, Any]] = []
    reviewed_url_key_count = 0
    if not include_reviewed_urls:
        reviewed_url_keys = load_reviewed_url_keys()
        # Also load any extra seen-URLs CSV specified in config (full cross-round dedup)
        extra_csv = cfg.get("discovery", "mediacloud", "previously_reviewed_urls_csv")
        if extra_csv:
            extra_path = Path(extra_csv)
            if extra_path.exists():
                from crawler.review_dedupe import url_keys as _url_keys
                for row in read_csv(extra_path):
                    u = row.get("url", "").strip()
                    if u:
                        reviewed_url_keys.update(_url_keys(u))
                print(f"Loaded extra seen-URLs for dedup: {extra_path} ({len(reviewed_url_keys)} keys total)")
        reviewed_url_key_count = len(reviewed_url_keys)
        records, previously_reviewed = split_new_review_rows(records, reviewed_url_keys)
        write_csv(
            output_dir / "metadata_previously_reviewed_urls.csv",
            previously_reviewed,
            output_columns(previously_reviewed) if previously_reviewed else BASE_DISCOVERY_COLUMNS,
        )
    rows = []
    for record in records:
        query_family = query_family_from_record(record)
        title = record.get("title_snippet") or ""
        url = record.get("url") or ""
        query = record.get("query_used") or ""
        decision = classify_oil_relevance(title=title, text="", url=url)

        # Proximity/title queries are meaningful search evidence even when
        # MediaCloud title snippets are abbreviated.
        priority = crawl_priority(query_family, record, decision)
        row = {
            "article_id": record.get("id") or "",
            "title": title,
            "source": record.get("source") or "",
            "date": record.get("published_date") or "",
            "url": url,
            "file_path": "",
            "query_family": query_family,
            "query_id": query_id_from_query(query),
            "query_used": query,
            "crawl_priority": priority,
            **decision.to_dict(),
        }
        rows.append(row)

    write_review_outputs(output_dir, rows, prefix="metadata")
    write_csv(output_dir / "crawl_queue.csv", crawl_queue_rows(rows), CRAWL_QUEUE_COLUMNS)
    write_summary(
        output_dir / "metadata_filtering_summary.json",
        rows,
        stage="metadata",
        extra={
            "previously_reviewed_urls_excluded": len(previously_reviewed),
            "reviewed_url_key_count": reviewed_url_key_count,
            "include_reviewed_urls": include_reviewed_urls,
        },
    )
    print(f"Metadata records classified: {len(rows)}")
    if previously_reviewed:
        print(f"Previously reviewed URLs excluded: {len(previously_reviewed)}")
    print(f"Crawl queue rows: {len(crawl_queue_rows(rows))}")


def run_crawl_stage(cfg: Config, output_dir: Path, limit: int = 0) -> None:
    queue_path = output_dir / "crawl_queue.csv"
    if not queue_path.exists():
        raise FileNotFoundError(f"Run metadata stage first: {queue_path}")
    queue = read_csv(queue_path)
    if limit:
        queue = queue[:limit]

    storage = Storage(cfg)
    downloader = Downloader(cfg)
    extractor = Extractor(cfg)

    success = failed = blocked = skipped_existing = 0
    for index, row in enumerate(queue, start=1):
        url = row["url"]
        existing = storage.get_article(url)
        if existing and existing.get("article_text"):
            skipped_existing += 1
            continue

        print(f"[{index}/{len(queue)}] {row.get('crawl_priority')} {url}")
        result = downloader.download(url)
        status = result["status"]
        storage.mark_discovered_status(url, status)
        if status != "success":
            if status == "robots_blocked":
                blocked += 1
            else:
                failed += 1
            continue

        html = result.get("raw_html") or ""
        extracted = extractor.extract(result.get("url") or url, html, raw_html_path=result.get("raw_html_path"))
        article = {
            "url": result.get("url") or url,
            "canonical_url": extracted.get("canonical_url") or result.get("url") or url,
            "title": extracted.get("title") or row.get("title"),
            "domain": row.get("domain") or record_domain(url),
            "source": row.get("source"),
            "publication_date": extracted.get("publication_date") or row.get("date"),
            "discovered_at": "",
            "query_used": row.get("query_used"),
            "discovery_method": "mediacloud_relevance_pipeline",
            "raw_html_path": result.get("raw_html_path"),
            "cleaned_text_path": extracted.get("cleaned_text_path"),
            "article_text": extracted.get("article_text"),
            "extraction_status": extracted.get("extraction_status"),
            "extraction_method": extracted.get("extraction_method"),
            "error_message": extracted.get("error_message"),
            "word_count": extracted.get("word_count") or 0,
        }
        storage.save_article(article)
        if extracted.get("article_text"):
            success += 1
        else:
            failed += 1

    downloader.close()
    storage.close()
    summary = {
        "created_at": utc_now(),
        "queued": len(queue),
        "success_with_text": success,
        "failed_or_no_text": failed,
        "robots_blocked": blocked,
        "skipped_existing_with_text": skipped_existing,
    }
    (output_dir / "crawl_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def run_rules_stage(cfg: Config, output_dir: Path) -> None:
    metadata_rows = {row["url"]: row for row in read_csv(output_dir / "metadata_all_articles_review.csv")}
    articles = read_articles(cfg.path("db"))
    rows = []
    for article in articles:
        url = article.get("url") or ""
        meta = metadata_rows.get(url, {})
        title = article.get("title") or meta.get("title") or ""
        text = article.get("article_text") or ""
        decision = classify_oil_relevance(title=title, text=text, url=url)
        rows.append(
            {
                "article_id": article.get("article_id") or meta.get("article_id") or "",
                "title": title,
                "source": article.get("source") or meta.get("source") or "",
                "date": article.get("publication_date") or meta.get("date") or "",
                "url": url,
                "file_path": article.get("cleaned_text_path") or article.get("raw_html_path") or "",
                "query_family": meta.get("query_family") or query_family_from_query(article.get("query_used") or ""),
                "query_id": meta.get("query_id") or query_id_from_query(article.get("query_used") or ""),
                "word_count": article.get("word_count") or "",
                **decision.to_dict(),
                "llm_label": "",
                "llm_confidence": "",
                "llm_reason": "",
                "llm_model": "",
            }
        )
    write_review_outputs(output_dir, rows, prefix="rule_text")
    write_summary(output_dir / "rule_text_filtering_summary.json", rows, stage="rule_text")
    print(f"Extracted article texts classified by rules: {len(rows)}")


def run_llm_stage(cfg: Config, output_dir: Path, model: str, limit: int = 0) -> None:
    rule_path = output_dir / "rule_text_all_articles_review.csv"
    if not rule_path.exists():
        raise FileNotFoundError(f"Run rules stage first: {rule_path}")
    rule_rows = read_csv(rule_path)
    articles = {row["url"]: row for row in read_articles(cfg.path("db"))}
    targets = [row for row in rule_rows if row.get("rule_candidate") == "True"]
    if limit:
        targets = targets[:limit]

    out_path = output_dir / "llm_results.jsonl"
    done_urls = load_done_llm_urls(out_path)
    with out_path.open("a", encoding="utf-8") as handle:
        for index, row in enumerate(targets, start=1):
            url = row["url"]
            if url in done_urls:
                continue
            article = articles.get(url, {})
            print(f"[LLM {index}/{len(targets)}] {url}")
            try:
                llm = ollama_relevance_check(
                    title=row.get("title") or "",
                    text=article.get("article_text") or "",
                    url=url,
                    model=model,
                )
            except Exception as exc:
                llm = {
                    "llm_label": "unclear",
                    "llm_confidence": 0.0,
                    "llm_reason": f"LLM call failed: {exc}",
                    "evidence_phrase": "",
                    "llm_model": model,
                }
            payload = {"url": url, **llm}
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
    print(f"LLM results written: {out_path}")


def run_outputs_stage(cfg: Config, output_dir: Path) -> None:
    rule_path = output_dir / "rule_text_all_articles_review.csv"
    if rule_path.exists():
        base_rows = read_csv(rule_path)
    else:
        base_rows = read_csv(output_dir / "metadata_all_articles_review.csv")

    llm_by_url = load_llm_results(output_dir / "llm_results.jsonl")
    rows = []
    for row in base_rows:
        rule = classify_oil_relevance(title=row.get("title", ""), text="", url=row.get("url", ""))
        # Preserve text-rule decision when available, then merge LLM fields.
        rule.rule_candidate = row.get("rule_candidate") == "True"
        rule.oil_role = row.get("oil_role") or rule.oil_role
        rule.final_label = row.get("final_label") or rule.final_label
        rule.confidence = _to_float(row.get("confidence"), rule.confidence)
        rule.reason = row.get("reason") or rule.reason
        rule.evidence_phrase = row.get("evidence_phrase") or rule.evidence_phrase
        rule.edible_oil_terms = split_terms(row.get("edible_oil_terms", ""))
        rule.adulteration_action_terms = split_terms(row.get("adulteration_action_terms", ""))
        rule.negative_terms = split_terms(row.get("negative_terms", ""))
        merged = {
            **{k: row.get(k, "") for k in BASE_COLUMNS if k in row},
            **merge_rule_and_llm(rule, llm_by_url.get(row.get("url", ""))),
        }
        rows.append(merged)

    write_review_outputs(output_dir, rows, prefix="")
    write_summary(output_dir / "filtering_summary.json", rows, stage="final")
    write_validation_sample(output_dir / "manual_validation_sample.csv", rows)
    print(f"Final rows written: {len(rows)}")


def read_discovered(db_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT id, url, discovery_method, query_used, discovered_at,
                   title_snippet, source, domain, published_date, status
            FROM discovered_urls
            ORDER BY published_date DESC, id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def read_articles(db_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM articles WHERE article_text IS NOT NULL").fetchall()
    return [dict(row) for row in rows]


def query_family_from_record(record: dict[str, Any]) -> str:
    method = record.get("discovery_method") or ""
    if method.startswith("mediacloud_"):
        return method.removeprefix("mediacloud_")
    return query_family_from_query(record.get("query_used") or "")


def query_family_from_query(query: str) -> str:
    if "article_title:" in query:
        return "title_only"
    if "~" in query:
        return "proximity"
    return "boolean"


def query_id_from_query(query: str) -> str:
    q = query.lower()
    has_fraud_signal = any(
        signal in q
        for signal in [
            "adulterat*",
            "contaminat*",
            "misbrand*",
            "substandard",
            "spurious",
            "fake",
            "counterfeit",
            "rancid",
            "unsafe oil",
            "mixed with",
        ]
    )
    has_enforcement_signal = any(
        signal in q
        for signal in [
            "fssai",
            "food safety",
            "raid*",
            "seiz*",
            "lab test",
            "quality test",
            "inspection",
            "crackdown",
        ]
    )
    if "article_title:" in q and "fssai" in q:
        return "title_oils_enforcement"
    if "article_title:" in q and "mustard oil" in q:
        return "title_named_oils_fraud"
    if "article_title:" in q:
        return "title_core_oils_fraud"
    if "~" in q:
        phrase = q.split('"')[1] if '"' in q else q[:40]
        return "proximity_" + "_".join(phrase.split())
    if has_enforcement_signal and not has_fraud_signal:
        return "boolean_oils_enforcement_only"
    if has_enforcement_signal and has_fraud_signal:
        return "boolean_oils_enforcement_evidence"
    if "mustard oil" in q:
        return "boolean_named_oils_fraud"
    return "boolean_core_oils_fraud"


def crawl_priority(query_family: str, record: dict[str, Any], decision: Any) -> str:
    query_id = query_id_from_query(record.get("query_used") or "")
    if decision.final_label == "relevant":
        return "high"
    if query_family == "title_only" and decision.rule_candidate:
        return "high"
    if query_family == "proximity" and query_id not in {"proximity_oil_seized"} and decision.final_label != "irrelevant":
        return "high"
    if decision.final_label == "manual_review":
        return "medium"
    if query_family == "title_only" and decision.oil_role != "non_food_oil":
        return "medium"
    # Phrase/boolean queries that return adjacent_or_unclear have real oil+enforcement signal
    # — don't drop them; let the ML classifier decide after crawling.
    if query_family in {"phrase", "boolean"} and decision.final_label != "irrelevant":
        return "medium"
    return "drop"


def crawl_queue_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = [row for row in rows if row.get("crawl_priority") in {"high", "medium"}]
    priority_order = {"high": 0, "medium": 1}
    queue.sort(
        key=lambda row: (
            priority_order.get(row.get("crawl_priority", ""), 9),
            row.get("date", ""),
            row.get("url", ""),
        ),
        reverse=False,
    )
    return [{key: row.get(key, "") for key in CRAWL_QUEUE_COLUMNS} for row in queue]


def write_review_outputs(output_dir: Path, rows: list[dict[str, Any]], prefix: str) -> None:
    stem = f"{prefix}_" if prefix else ""
    fieldnames = output_columns(rows)
    write_csv(output_dir / f"{stem}all_articles_review.csv", rows, fieldnames)
    write_csv(
        output_dir / f"{stem}relevant_oil_articles.csv",
        [row for row in rows if row.get("final_label") == "relevant"],
        fieldnames,
    )
    write_csv(
        output_dir / f"{stem}manual_review_articles.csv",
        [row for row in rows if row.get("final_label") == "manual_review"],
        fieldnames,
    )
    write_csv(
        output_dir / f"{stem}irrelevant_articles.csv",
        [row for row in rows if row.get("final_label") == "irrelevant"],
        fieldnames,
    )


def write_summary(
    path: Path,
    rows: list[dict[str, Any]],
    stage: str,
    extra: dict[str, Any] | None = None,
) -> None:
    labels = Counter(row.get("final_label", "") for row in rows)
    roles = Counter(row.get("oil_role", "") for row in rows)
    payload = {
        "created_at": utc_now(),
        "stage": stage,
        "total_articles_loaded": len(rows),
        "rule_candidates": sum(1 for row in rows if str(row.get("rule_candidate")) == "True"),
        "relevant_articles": labels.get("relevant", 0),
        "irrelevant_articles": labels.get("irrelevant", 0),
        "manual_review_articles": labels.get("manual_review", 0),
        "non_food_oil_articles": roles.get("non_food_oil", 0),
        "oil_only_adulterant_articles": roles.get("adulterant", 0),
        "oil_role_counts": dict(roles),
        "final_label_counts": dict(labels),
    }
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_validation_sample(path: Path, rows: list[dict[str, Any]]) -> None:
    relevant = [row for row in rows if row.get("final_label") == "relevant"][:100]
    irrelevant = [row for row in rows if row.get("final_label") == "irrelevant"][:100]
    manual = [row for row in rows if row.get("final_label") == "manual_review"][:100]
    sample = []
    seen = set()
    for row in relevant + irrelevant + manual:
        if row.get("url") in seen:
            continue
        seen.add(row.get("url"))
        sample.append({**row, "manual_label": ""})
    write_csv(path, sample, output_columns(sample) + ["manual_label"])


def load_done_llm_urls(path: Path) -> set[str]:
    return set(load_llm_results(path))


def load_llm_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    results = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("url"):
                results[row["url"]] = row
    return results


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def output_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns = list(BASE_COLUMNS)
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns


def record_domain(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc.lower().removeprefix("www.")


def split_terms(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


BASE_COLUMNS = [
    "article_id",
    "title",
    "source",
    "date",
    "url",
    "file_path",
    "query_family",
    "query_id",
    "rule_candidate",
    "oil_role",
    "final_label",
    "confidence",
    "reason",
    "evidence_phrase",
    "edible_oil_terms",
    "adulteration_action_terms",
    "negative_terms",
    "llm_label",
    "llm_confidence",
    "llm_reason",
    "llm_model",
]

BASE_DISCOVERY_COLUMNS = [
    "id",
    "url",
    "discovery_method",
    "query_used",
    "discovered_at",
    "title_snippet",
    "source",
    "domain",
    "published_date",
    "status",
]

CRAWL_QUEUE_COLUMNS = [
    "article_id",
    "title",
    "source",
    "date",
    "url",
    "query_family",
    "query_id",
    "query_used",
    "crawl_priority",
    "oil_role",
    "final_label",
    "confidence",
    "reason",
    "evidence_phrase",
]


if __name__ == "__main__":
    raise SystemExit(main())
