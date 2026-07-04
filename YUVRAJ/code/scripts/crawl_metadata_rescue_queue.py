from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crawler.config import Config
from crawler.downloader import Downloader
from crawler.extractor import Extractor
from crawler.review_dedupe import load_reviewed_url_keys, split_new_review_rows
from crawler.storage import Storage


DEFAULT_CONFIG = ROOT / "config" / "config_edible_oils_combined.yaml"
DEFAULT_OUTPUT_DIR = ROOT / Path(
    "data/runs/edible_oil_adulteration_round_02_2026-06-23/"
    "mediacloud/outputs/oil_relevance"
)

LOG_COLUMNS = [
    "url",
    "status",
    "http_status",
    "word_count",
    "title",
    "source",
    "date",
    "query_family",
    "query_id",
    "extraction_status",
    "extraction_method",
    "raw_html_path",
    "cleaned_text_path",
    "error_message",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl strict metadata-rescue candidates from the edible-oil audit."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--queue", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--use-playwright", action="store_true", default=True)
    parser.add_argument("--playwright-first", action="store_true")
    parser.add_argument("--ignore-robots", action="store_true")
    parser.add_argument(
        "--include-reviewed-urls",
        action="store_true",
        help="Keep URLs already human-marked in previous rounds in the rescue crawl.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in LOG_COLUMNS})


def configure_rescue_crawl(
    cfg: Config,
    timeout: int,
    delay: float,
    use_playwright: bool,
    playwright_first: bool,
    ignore_robots: bool,
) -> None:
    crawl = cfg.raw.setdefault("crawl", {})
    crawl["respect_robots_txt"] = not ignore_robots
    crawl["use_playwright"] = use_playwright
    crawl["playwright_first"] = playwright_first
    crawl["timeout_seconds"] = timeout
    crawl["delay_seconds"] = delay
    crawl["max_retries"] = 2


def record_domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def save_or_update(storage: Storage, article: dict[str, Any]) -> None:
    if storage.save_article(article):
        return
    storage.update_article(article["url"], {k: v for k, v in article.items() if k != "url"})


def get_discovered_status(db_path: Path, url: str) -> str:
    with sqlite3.connect(db_path) as con:
        row = con.execute("SELECT status FROM discovered_urls WHERE url=?", (url,)).fetchone()
    return row[0] if row else ""


def build_article(
    row: dict[str, str],
    result: dict[str, Any],
    extracted: dict[str, Any],
) -> dict[str, Any]:
    original_url = row["url"]
    final_url = result.get("url") or original_url
    return {
        "url": original_url,
        "canonical_url": extracted.get("canonical_url") or final_url,
        "title": extracted.get("title") or row.get("title"),
        "domain": record_domain(original_url),
        "source": row.get("source"),
        "publication_date": extracted.get("publication_date") or row.get("date"),
        "discovered_at": "",
        "query_used": row.get("query_used"),
        "discovery_method": "mediacloud_metadata_rescue",
        "raw_html_path": result.get("raw_html_path"),
        "cleaned_text_path": extracted.get("cleaned_text_path"),
        "article_text": extracted.get("article_text"),
        "extraction_status": extracted.get("extraction_status"),
        "extraction_method": extracted.get("extraction_method"),
        "error_message": extracted.get("error_message"),
        "word_count": extracted.get("word_count") or 0,
    }


def main() -> None:
    args = parse_args()
    cfg = Config(args.config)
    configure_rescue_crawl(
        cfg,
        timeout=args.timeout,
        delay=args.delay,
        use_playwright=args.use_playwright,
        playwright_first=args.playwright_first,
        ignore_robots=args.ignore_robots,
    )
    output_dir = args.output_dir
    queue_path = args.queue or output_dir / "metadata_rescue_crawl_queue.csv"
    queue = read_csv(queue_path)
    previously_reviewed: list[dict[str, str]] = []
    if not args.include_reviewed_urls:
        queue, previously_reviewed = split_new_review_rows(queue, load_reviewed_url_keys())
    if args.limit:
        queue = queue[: args.limit]

    storage = Storage(cfg)
    downloader = Downloader(cfg)
    extractor = Extractor(cfg)
    results: list[dict[str, Any]] = []
    summary = {
        "created_at": utc_now(),
        "queue_path": str(queue_path),
        "queued": len(queue),
        "respect_robots_txt": not args.ignore_robots,
        "use_playwright": args.use_playwright,
        "playwright_first": args.playwright_first,
        "success_with_text": 0,
        "success_no_text": 0,
        "failed": 0,
        "robots_blocked": 0,
        "skipped_existing_with_text": 0,
        "previously_reviewed_urls_excluded": len(previously_reviewed),
    }

    try:
        for index, row in enumerate(queue, start=1):
            url = row["url"]
            existing = storage.get_article(url)
            if existing and existing.get("article_text") and not args.force:
                summary["skipped_existing_with_text"] += 1
                results.append(
                    {
                        **row,
                        "status": "skipped_existing_with_text",
                        "word_count": existing.get("word_count") or 0,
                        "extraction_status": existing.get("extraction_status") or "",
                        "extraction_method": existing.get("extraction_method") or "",
                        "cleaned_text_path": existing.get("cleaned_text_path") or "",
                    }
                )
                continue

            print(f"[{index}/{len(queue)}] metadata rescue {url}", flush=True)
            result = downloader.download(url)
            status = result.get("status") or "failed"
            log_row: dict[str, Any] = {
                **row,
                "status": status,
                "http_status": result.get("http_status") or "",
                "raw_html_path": result.get("raw_html_path") or "",
                "error_message": result.get("error_message") or "",
            }

            if status != "success":
                if status == "robots_blocked":
                    summary["robots_blocked"] += 1
                else:
                    summary["failed"] += 1
                storage.mark_discovered_status(url, "metadata_rescue_failed")
                results.append(log_row)
                continue

            extracted = extractor.extract(
                result.get("url") or url,
                result.get("raw_html") or "",
                raw_html_path=result.get("raw_html_path"),
            )
            article = build_article(row, result, extracted)
            save_or_update(storage, article)

            if extracted.get("article_text"):
                summary["success_with_text"] += 1
                storage.mark_discovered_status(url, "downloaded_metadata_rescue")
            else:
                summary["success_no_text"] += 1
                storage.mark_discovered_status(url, "metadata_rescue_no_text")

            log_row.update(
                {
                    "title": article.get("title") or row.get("title"),
                    "word_count": article.get("word_count") or 0,
                    "extraction_status": extracted.get("extraction_status") or "",
                    "extraction_method": extracted.get("extraction_method") or "",
                    "cleaned_text_path": extracted.get("cleaned_text_path") or "",
                    "error_message": extracted.get("error_message") or "",
                }
            )
            results.append(log_row)
    finally:
        downloader.close()
        storage.close()

    summary["final_status_counts_for_queue"] = {
        row["url"]: get_discovered_status(cfg.path("db"), row["url"]) for row in queue
    }
    summary_path = output_dir / "metadata_rescue_crawl_summary.json"
    log_path = output_dir / "metadata_rescue_crawl_log.csv"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_csv(log_path, results)
    print(json.dumps(summary, indent=2))
    print(f"Rescue crawl log written: {log_path.resolve()}")


if __name__ == "__main__":
    main()
