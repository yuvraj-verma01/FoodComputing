from __future__ import annotations

import argparse
import csv
import json
import re
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
from crawler.storage import Storage


DEFAULT_CONFIG = ROOT / "config" / "config_edible_oils_combined.yaml"
DEFAULT_OUTPUT_DIR = ROOT / Path(
    "data/runs/edible_oils_boolean_title_proximity_2026-06-22/"
    "mediacloud/outputs/oil_relevance"
)

LOG_COLUMNS = [
    "url",
    "attempted_url",
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
        description="Retry robots-blocked edible-oil URLs with Playwright."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument(
        "--status",
        default="robots_blocked",
        help="discovered_urls.status value to retry.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Retry even when an article row with text already exists.",
    )
    parser.add_argument(
        "--variants",
        action="store_true",
        help="Try public AMP/mobile URL variants after the original URL fails.",
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


def load_status_urls(db_path: Path, status: str) -> set[str]:
    with sqlite3.connect(db_path) as con:
        rows = con.execute(
            "SELECT url FROM discovered_urls WHERE status=?", (status,)
        ).fetchall()
    return {row[0] for row in rows}


def record_domain(url: str) -> str:
    return urlparse(url).netloc.removeprefix("www.")


def url_variants(url: str) -> list[str]:
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    base = f"{parsed.scheme}://{host}"
    variants = [url]

    def add(candidate: str) -> None:
        if candidate not in variants:
            variants.append(candidate)

    if "news18.com" in host:
        add(f"{base}/amp{path}{query}")
        add(f"{base}{path}/amp{query}")
    elif "business-standard.com" in host:
        add(f"{base}/amp{path}{query}")
        if path.startswith("/article/"):
            add(f"{base}/amp{path}{query}")
    elif "ndtv.com" in host:
        add(f"{base}/amp{path}{query}")
        add(f"{base}{path}/amp/1{query}")
        add(f"{base}{path}?amp=1")
    elif "firstpost.com" in host:
        add(f"{base}/amp{path}{query}")
    elif "moneycontrol.com" in host:
        add(f"{base}{path}/amp{query}")
        add(f"{base}/amp{path}{query}")

    return variants


def configure_retry(cfg: Config, timeout: int, delay: float) -> None:
    crawl = cfg.raw.setdefault("crawl", {})
    crawl["respect_robots_txt"] = False
    crawl["use_playwright"] = True
    crawl["playwright_first"] = True
    crawl["timeout_seconds"] = timeout
    crawl["delay_seconds"] = delay
    crawl["max_retries"] = 1


def build_article(
    original_url: str,
    queue_row: dict[str, str],
    result: dict[str, Any],
    extracted: dict[str, Any],
) -> dict[str, Any]:
    final_url = result.get("url") or original_url
    return {
        "url": original_url,
        "canonical_url": extracted.get("canonical_url") or final_url,
        "title": extracted.get("title") or queue_row.get("title"),
        "domain": queue_row.get("domain") or record_domain(original_url),
        "source": queue_row.get("source"),
        "publication_date": extracted.get("publication_date") or queue_row.get("date"),
        "discovered_at": "",
        "query_used": queue_row.get("query_used"),
        "discovery_method": "mediacloud_playwright_robot_retry",
        "raw_html_path": result.get("raw_html_path"),
        "cleaned_text_path": extracted.get("cleaned_text_path"),
        "article_text": extracted.get("article_text"),
        "extraction_status": extracted.get("extraction_status"),
        "extraction_method": extracted.get("extraction_method"),
        "error_message": extracted.get("error_message"),
        "word_count": extracted.get("word_count") or 0,
    }


def save_or_update(storage: Storage, article: dict[str, Any]) -> None:
    if storage.save_article(article):
        return
    updates = {k: v for k, v in article.items() if k != "url"}
    storage.update_article(article["url"], updates)


def safe_suffix(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")


def main() -> None:
    args = parse_args()
    cfg = Config(args.config)
    configure_retry(cfg, timeout=args.timeout, delay=args.delay)
    output_dir = args.output_dir

    queue_rows = read_csv(output_dir / "crawl_queue.csv")
    queue_by_url = {row["url"]: row for row in queue_rows}
    status_urls = load_status_urls(cfg.path("db"), args.status)
    retry_rows = [row for row in queue_rows if row["url"] in status_urls]
    if args.limit:
        retry_rows = retry_rows[: args.limit]

    storage = Storage(cfg)
    downloader = Downloader(cfg)
    extractor = Extractor(cfg)

    results: list[dict[str, Any]] = []
    summary = {
        "created_at": utc_now(),
        "status_filter": args.status,
        "queued": len(retry_rows),
        "success_with_text": 0,
        "success_no_text": 0,
        "failed": 0,
        "skipped_existing_with_text": 0,
    }

    try:
        for index, row in enumerate(retry_rows, start=1):
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
                    }
                )
                continue

            print(f"[{index}/{len(retry_rows)}] Playwright retry {url}", flush=True)
            variants = url_variants(url) if args.variants else [url]
            result: dict[str, Any] = {"status": "failed", "error_message": "No variants attempted"}
            attempted_url = url
            for variant in variants:
                attempted_url = variant
                if variant != url:
                    print(f"  variant {variant}", flush=True)
                result = downloader.download(variant)
                if result.get("status") == "success":
                    break
            status = result.get("status") or "failed"

            log_row: dict[str, Any] = {
                **row,
                "attempted_url": attempted_url,
                "status": status,
                "http_status": result.get("http_status") or "",
                "raw_html_path": result.get("raw_html_path") or "",
                "error_message": result.get("error_message") or "",
            }

            if status != "success":
                summary["failed"] += 1
                storage.mark_discovered_status(url, "playwright_retry_failed")
                results.append(log_row)
                continue

            html = result.get("raw_html") or ""
            extracted = extractor.extract(
                result.get("url") or url,
                html,
                raw_html_path=result.get("raw_html_path"),
            )
            article = build_article(url, queue_by_url.get(url, row), result, extracted)
            save_or_update(storage, article)

            text_ok = bool(extracted.get("article_text"))
            if text_ok:
                summary["success_with_text"] += 1
                storage.mark_discovered_status(url, "downloaded_playwright_retry")
            else:
                summary["success_no_text"] += 1
                storage.mark_discovered_status(url, "playwright_retry_no_text")

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

    suffix = "" if args.status == "robots_blocked" else f"_{safe_suffix(args.status)}"
    if args.variants:
        suffix = f"{suffix}_variants"
    summary_path = output_dir / f"playwright_robot_retry{suffix}_summary.json"
    log_path = output_dir / f"playwright_robot_retry{suffix}_log.csv"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_csv(log_path, results)
    print(json.dumps(summary, indent=2))
    print(f"Retry log written: {log_path.resolve()}")


if __name__ == "__main__":
    main()
