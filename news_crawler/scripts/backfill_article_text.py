"""Backfill article_text for master corpus rows that have empty text.

Two sources:
  1. Round 3 SQLite DB  — articles were crawled but text wasn't pulled into master CSV
  2. Round 0 seeds      — never crawled; attempt Playwright crawl now
  3. Remaining blocked  — news18 / ndtv / business-standard that can't be fetched

Updates master_all_articles.csv, master_relevant_articles.csv,
master_irrelevant_articles.csv, master_corpus_readable.csv in-place.
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.stdout.reconfigure(encoding="utf-8")

from crawler.config import Config
from crawler.downloader import Downloader
from crawler.extractor import Extractor
from crawler.storage import Storage

MASTER_DIR = ROOT / "reports" / "master_corpus"
R3_DB      = ROOT / "data/runs/edible_oil_adulteration_round_03_2026-06-23/mediacloud/outputs/articles.db"
R3_RUN_CFG = ROOT / "config" / "config_edible_oils_round3.yaml"

READABLE_COLS = [
    "round_number", "final_keep", "final_human_label", "title", "source",
    "date", "url", "domain", "oil_role", "model_final_label", "model_confidence",
    "reason", "evidence_phrase", "query_family", "query_id", "human_review_status",
    "word_count",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(p: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  Written: {p.name}  ({len(rows)} rows)")


def r3_db_texts(db_path: Path) -> dict[str, dict]:
    """Return {url: {article_text, word_count, cleaned_text_path}} from Round 3 DB."""
    if not db_path.exists():
        print(f"WARNING: Round 3 DB not found at {db_path}")
        return {}
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT url, article_text, word_count, cleaned_text_path "
            "FROM articles WHERE article_text IS NOT NULL AND article_text != ''"
        ).fetchall()
    return {r["url"]: dict(r) for r in rows if r["url"]}


def crawl_urls_with_playwright(urls: list[str]) -> dict[str, dict]:
    """Crawl a list of URLs with Playwright + robots bypass. Returns {url: {text, wc}}."""
    if not urls:
        return {}

    cfg = Config(R3_RUN_CFG)
    crawl = cfg.raw.setdefault("crawl", {})
    crawl["respect_robots_txt"] = False
    crawl["use_playwright"]     = True
    crawl["playwright_first"]   = True
    crawl["timeout_seconds"]    = 60
    crawl["delay_seconds"]      = 2.0
    crawl["max_retries"]        = 2

    downloader = Downloader(cfg)
    extractor  = Extractor(cfg)
    results: dict[str, dict] = {}

    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url[:90]}", flush=True)
        result = downloader.download(url)
        if result.get("status") != "success":
            print(f"     -> failed: {result.get('error_message','')[:60]}", flush=True)
            continue
        html      = result.get("raw_html") or ""
        final_url = result.get("url") or url
        ext = extractor.extract(final_url, html, raw_html_path=result.get("raw_html_path"))
        text = ext.get("article_text") or ""
        wc   = ext.get("word_count") or 0
        if text:
            results[url] = {
                "article_text":       text,
                "word_count":         wc,
                "cleaned_text_path":  ext.get("cleaned_text_path") or "",
            }
            print(f"     -> ok ({wc} words)", flush=True)
        else:
            print(f"     -> crawled but no text", flush=True)

    downloader.close()
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    master_path = MASTER_DIR / "master_all_articles.csv"
    rows = read_csv(master_path)
    fieldnames = list(rows[0].keys()) if rows else []

    empty_rows = [r for r in rows if not (r.get("article_text") or "").strip()]
    print(f"Master corpus: {len(rows)} rows | empty article_text: {len(empty_rows)}")

    # ── Source 1: Round 3 DB ──────────────────────────────────────────────────
    print(f"\nLoading Round 3 SQLite DB ...")
    r3_texts = r3_db_texts(R3_DB)
    print(f"  Found {len(r3_texts)} articles with text in Round 3 DB")

    r3_matched = 0
    for r in empty_rows:
        url = r.get("url", "")
        if url in r3_texts:
            r["article_text"]      = r3_texts[url]["article_text"]
            r["word_count"]        = str(r3_texts[url].get("word_count") or "")
            r["cleaned_text_path"] = r3_texts[url].get("cleaned_text_path") or ""
            r3_matched += 1

    print(f"  Backfilled from Round 3 DB: {r3_matched}")

    # ── Source 2: Crawl remaining empties (seeds + any others) ───────────────
    still_empty = [r for r in rows if not (r.get("article_text") or "").strip()]
    print(f"\nStill empty after DB lookup: {len(still_empty)}")
    crawl_urls = [r["url"] for r in still_empty if r.get("url")]

    if crawl_urls:
        print(f"Crawling {len(crawl_urls)} URLs with Playwright ...")
        crawled = crawl_urls_with_playwright(crawl_urls)
        print(f"\nSuccessfully crawled: {len(crawled)}/{len(crawl_urls)}")

        crawl_matched = 0
        for r in still_empty:
            url = r.get("url", "")
            if url in crawled:
                r["article_text"]      = crawled[url]["article_text"]
                r["word_count"]        = str(crawled[url].get("word_count") or "")
                r["cleaned_text_path"] = crawled[url].get("cleaned_text_path") or ""
                crawl_matched += 1
        print(f"Backfilled from fresh crawl: {crawl_matched}")

    # ── Final state ───────────────────────────────────────────────────────────
    still_empty_final = [r for r in rows if not (r.get("article_text") or "").strip()]
    has_text = len(rows) - len(still_empty_final)
    print(f"\nFinal state:")
    print(f"  Total rows   : {len(rows)}")
    print(f"  Has text     : {has_text}")
    print(f"  Still empty  : {len(still_empty_final)}")
    if still_empty_final:
        print(f"  Blocked/unfetchable:")
        for r in still_empty_final:
            print(f"    [{r.get('final_keep')}] {(r.get('title') or '')[:65]}")

    # ── Write updated master files ────────────────────────────────────────────
    print(f"\nWriting updated master corpus ...")
    relevant   = [r for r in rows if str(r.get("final_keep")) == "1"]
    irrelevant = [r for r in rows if str(r.get("final_keep")) == "0"]

    write_csv(master_path,                              rows,       fieldnames)
    write_csv(MASTER_DIR / "master_relevant_articles.csv",   relevant,   fieldnames)
    write_csv(MASTER_DIR / "master_irrelevant_articles.csv", irrelevant, fieldnames)
    write_csv(MASTER_DIR / "master_corpus_readable.csv",     relevant,   READABLE_COLS)

    print(f"Done. Training-ready rows: {has_text} "
          f"(+{has_text - 308} vs before)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
