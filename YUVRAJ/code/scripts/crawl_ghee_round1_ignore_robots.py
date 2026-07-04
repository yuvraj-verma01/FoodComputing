"""Crawl ghee Round 1 discovered URLs with robots checks disabled.

The URL discovery step only collects URLs. This script attempts article-page
download and text extraction for every pending discovered URL in the ghee Round
1 database, using normal HTTP first and Playwright fallback when needed.
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
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.config import Config
from crawler.downloader import Downloader
from crawler.extractor import Extractor
from crawler.storage import Storage


DEFAULT_CONFIG = ROOT / "config" / "config_ghee_round1.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--limit", type=int, default=0, help="0 means all pending URLs.")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument(
        "--statuses",
        nargs="+",
        default=["pending"],
        help="Discovered URL statuses to crawl. Default: pending.",
    )
    parser.add_argument(
        "--playwright-first",
        action="store_true",
        help="Use Playwright before normal HTTP. Default is HTTP first, Playwright fallback.",
    )
    args = parser.parse_args()

    cfg = Config(args.config)
    configure_crawl(cfg, args)
    output_dir = cfg.path("outputs")
    log_path = output_dir / "ghee_round1_crawl_ignore_robots_log.csv"
    summary_path = output_dir / "ghee_round1_crawl_ignore_robots_summary.json"

    storage = Storage(cfg)
    downloader = Downloader(cfg)
    extractor = Extractor(cfg)

    pending = get_urls_by_status(storage, args.statuses, limit=args.limit)
    print(f"Pending URLs to crawl: {len(pending)}")
    print(f"Statuses included: {', '.join(args.statuses)}")
    print("robots.txt checks: disabled")
    print(f"Playwright fallback: enabled; playwright_first={args.playwright_first}")

    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    text_counts: Counter[str] = Counter()

    for index, url_rec in enumerate(pending, start=1):
        url = url_rec["url"]
        print(f"[{index}/{len(pending)}] {url[:140]}", flush=True)
        result = downloader.download(url)
        download_status = result.get("status") or "failed"
        storage.mark_discovered_status(url, download_status)
        counts[download_status] += 1

        article_text = ""
        extraction_status = ""
        extraction_method = ""
        word_count = 0
        cleaned_text_path = ""
        title = url_rec.get("title_snippet") or ""
        final_url = result.get("url") or url

        if download_status == "success":
            html = result.get("raw_html") or ""
            extracted = extractor.extract(final_url, html, result.get("raw_html_path"))
            extraction_status = extracted.get("extraction_status") or "failed"
            extraction_method = extracted.get("extraction_method") or ""
            article_text = extracted.get("article_text") or ""
            word_count = int(extracted.get("word_count") or 0)
            cleaned_text_path = extracted.get("cleaned_text_path") or ""
            title = extracted.get("title") or title
            text_counts[extraction_status] += 1

            article = {
                **extracted,
                "url": final_url,
                "canonical_url": extracted.get("canonical_url") or final_url,
                "domain": extracted.get("domain") or url_rec.get("domain"),
                "source": url_rec.get("source"),
                "query_used": url_rec.get("query_used"),
                "discovery_method": url_rec.get("discovery_method"),
                "raw_html_path": result.get("raw_html_path"),
                "discovered_at": url_rec.get("discovered_at"),
            }
            storage.save_article(article)
            if article_text:
                storage.mark_discovered_status(url, "downloaded_ignore_robots")
        else:
            text_counts["not_downloaded"] += 1

        rows.append(
            {
                "index": index,
                "url": url,
                "final_url": final_url,
                "domain": url_rec.get("domain") or "",
                "source": url_rec.get("source") or "",
                "published_date": url_rec.get("published_date") or "",
                "title": title,
                "query_used": url_rec.get("query_used") or "",
                "discovery_method": url_rec.get("discovery_method") or "",
                "download_status": download_status,
                "http_status": result.get("http_status") or "",
                "download_error": result.get("error_message") or "",
                "raw_html_path": result.get("raw_html_path") or "",
                "extraction_status": extraction_status,
                "extraction_method": extraction_method,
                "word_count": word_count,
                "cleaned_text_path": cleaned_text_path,
                "text_preview": article_text[:800].replace("\r", " ").replace("\n", " "),
            }
        )
        print(
            f"  download={download_status} extract={extraction_status or '-'} words={word_count}",
            flush=True,
        )

    write_csv(log_path, rows, list(rows[0].keys()) if rows else [])
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": str(args.config),
        "pending_urls_attempted": len(pending),
        "download_status_counts": dict(sorted(counts.items())),
        "extraction_status_counts": dict(sorted(text_counts.items())),
        "respect_robots_txt": False,
        "use_playwright": True,
        "playwright_first": args.playwright_first,
        "timeout_seconds": args.timeout,
        "delay_seconds": args.delay,
        "max_retries": args.max_retries,
        "log_path": str(log_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    downloader.close()
    storage.export_csv()
    storage.export_jsonl()
    storage.close()

    print(json.dumps(summary, indent=2))
    return 0


def configure_crawl(cfg: Config, args: argparse.Namespace) -> None:
    crawl = cfg.raw.setdefault("crawl", {})
    crawl["respect_robots_txt"] = False
    crawl["use_playwright"] = True
    crawl["playwright_first"] = bool(args.playwright_first)
    crawl["timeout_seconds"] = int(args.timeout)
    crawl["delay_seconds"] = float(args.delay)
    crawl["max_retries"] = int(args.max_retries)


def get_urls_by_status(storage: Storage, statuses: list[str], limit: int = 0) -> list[dict[str, Any]]:
    statuses = [status.strip() for status in statuses if status.strip()]
    if not statuses:
        statuses = ["pending"]
    placeholders = ",".join("?" for _ in statuses)
    sql = f"SELECT * FROM discovered_urls WHERE status IN ({placeholders}) ORDER BY id ASC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = storage.conn.execute(sql, statuses).fetchall()
    return [dict(row) for row in rows]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
