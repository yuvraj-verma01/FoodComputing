"""Crawl the 6 robots-blocked metadata-rescue articles using Playwright.

These are articles you marked as keep=1 in metadata_reject_llm_human_reviewed.xlsx
but which failed crawl with robots_blocked status. Playwright bypasses robots.txt.

After this script succeeds, run append_metadata_rescue_to_round2.py with --force
to re-merge everything back into Round 2 + master corpus.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crawler.config import Config
from crawler.downloader import Downloader
from crawler.extractor import Extractor
from crawler.storage import Storage


DEFAULT_CONFIG = ROOT / "config" / "config_edible_oils_combined.yaml"
OUTPUT_DIR = ROOT / "data/runs/edible_oil_adulteration_round_02_2026-06-23/mediacloud/outputs/oil_relevance"

ROBOTS_BLOCKED_URLS = [
    {
        "url": "https://www.thehindu.com/news/national/andhra-pradesh/50-cases-registered-during-raids-on-oil-shops-in-ap/article65360803.ece",
        "title": "50 cases registered during raids on oil shops in A.P.",
        "source": "thehindu.com",
        "date": "",
    },
    {
        "url": "https://www.freepressjournal.in/mumbai/maharashtra-news-minister-narhari-zirwal-announces-suspension-of-2-fda-officials-closure-of-nandurbar-factory-over-oil-adulteration",
        "title": "Maharashtra News: Minister Narhari Zirwal Announces Suspension Of 2 FDA Officials, Closure Of Nandurbar Factory Over Oil Adulteration",
        "source": "freepressjournal.in",
        "date": "",
    },
    {
        "url": "https://www.thehindu.com/news/cities/Hyderabad/oils-not-well-food-safety-teams-smell-fraud/article65290089.ece",
        "title": "Oil's not well? Food safety teams smell fraud",
        "source": "thehindu.com",
        "date": "",
    },
    {
        "url": "https://www.freepressjournal.in/indore/madhya-pradesh-sale-of-loose-oil-only-through-vending-machine-collector",
        "title": "Madhya Pradesh: Sale of loose oil only through vending machine: Collector",
        "source": "freepressjournal.in",
        "date": "",
    },
    {
        "url": "https://www.thehindu.com/news/national/kerala/operation-oil-manufacturer-to-be-allowed-to-launch-only-one-brand-of-oil/article66144992.ece",
        "title": "Operation Oil: manufacturer to be allowed to launch only one brand of oil",
        "source": "thehindu.com",
        "date": "",
    },
    {
        "url": "https://www.thehansindia.com/news/cities/hyderabad/traders-given-15-days-to-halt-sale-of-loose-edible-oil-1069613",
        "title": "Traders given 15 days to halt sale of loose edible oil",
        "source": "thehansindia.com",
        "date": "",
    },
]

LOG_COLUMNS = [
    "url", "status", "http_status", "word_count", "title", "source",
    "date", "extraction_status", "extraction_method",
    "cleaned_text_path", "error_message",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def save_or_update(storage: Storage, article: dict) -> None:
    if not storage.save_article(article):
        storage.update_article(article["url"], {k: v for k, v in article.items() if k != "url"})


def main() -> None:
    cfg = Config(DEFAULT_CONFIG)
    # Force Playwright + ignore robots
    crawl = cfg.raw.setdefault("crawl", {})
    crawl["respect_robots_txt"] = False
    crawl["use_playwright"] = True
    crawl["playwright_first"] = True
    crawl["timeout_seconds"] = 60
    crawl["delay_seconds"] = 3.0
    crawl["max_retries"] = 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    storage = Storage(cfg)
    downloader = Downloader(cfg)
    extractor = Extractor(cfg)

    results = []
    summary = {
        "created_at": utc_now(),
        "queued": len(ROBOTS_BLOCKED_URLS),
        "success_with_text": 0,
        "success_no_text": 0,
        "failed": 0,
    }

    try:
        for i, row in enumerate(ROBOTS_BLOCKED_URLS, start=1):
            url = row["url"]
            print(f"[{i}/{len(ROBOTS_BLOCKED_URLS)}] Playwright crawl: {url}", flush=True)

            result = downloader.download(url)
            status = result.get("status") or "failed"

            log_row = {
                "url": url,
                "status": status,
                "http_status": result.get("http_status") or "",
                "title": row["title"],
                "source": row["source"],
                "date": row["date"],
                "error_message": result.get("error_message") or "",
            }

            if status != "success":
                print(f"  FAILED: {result.get('error_message','')}", flush=True)
                summary["failed"] += 1
                results.append({**log_row, "word_count": 0, "extraction_status": "failed",
                                 "extraction_method": "", "cleaned_text_path": ""})
                continue

            html = result.get("raw_html") or ""
            extracted = extractor.extract(result.get("url") or url, html)
            article = {
                "url": url,
                "canonical_url": extracted.get("canonical_url") or url,
                "title": extracted.get("title") or row["title"],
                "domain": record_domain(url),
                "source": row["source"],
                "publication_date": extracted.get("publication_date") or row["date"],
                "discovered_at": utc_now(),
                "query_used": "",
                "discovery_method": "mediacloud_metadata_rescue_playwright",
                "article_text": extracted.get("article_text"),
                "extraction_status": extracted.get("extraction_status"),
                "extraction_method": extracted.get("extraction_method"),
                "error_message": extracted.get("error_message"),
                "word_count": extracted.get("word_count") or 0,
                "cleaned_text_path": extracted.get("cleaned_text_path"),
            }
            save_or_update(storage, article)

            if extracted.get("article_text"):
                summary["success_with_text"] += 1
                print(f"  OK: {extracted.get('word_count',0)} words | {extracted.get('title','')[:60]}", flush=True)
            else:
                summary["success_no_text"] += 1
                print(f"  crawled but no text extracted", flush=True)

            log_row.update({
                "word_count": article["word_count"],
                "extraction_status": extracted.get("extraction_status") or "",
                "extraction_method": extracted.get("extraction_method") or "",
                "cleaned_text_path": extracted.get("cleaned_text_path") or "",
                "error_message": extracted.get("error_message") or "",
            })
            results.append(log_row)

    finally:
        downloader.close()
        storage.close()

    log_path = OUTPUT_DIR / "robots_blocked_playwright_retry_log.csv"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        writer.writeheader()
        for r in results:
            writer.writerow({col: r.get(col, "") for col in LOG_COLUMNS})

    summary_path = OUTPUT_DIR / "robots_blocked_playwright_retry_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
