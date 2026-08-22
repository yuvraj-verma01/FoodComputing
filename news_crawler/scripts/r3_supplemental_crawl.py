"""Round 3 supplemental crawl + full re-classification.

The main pipeline's metadata stage over-dropped tight phrase-query articles
(MediaCloud title snippets too short to show oil + adulteration together), and
its crawl stage hit robots.txt on the high-value FSSAI/raid articles.

This script:
  1. Gathers all target URLs = main crawl queue (high/medium) + tight phrase-query
     drops (excluding the noisy "adulterated food items" phrase).
  2. Crawls every target that lacks article text using PLAYWRIGHT with robots.txt
     bypass (config set BEFORE the Downloader is built — the Downloader caches these
     flags at init, so they must be set first).
  3. Rule-classifies all Round 3 articles that have text.
  4. Runs Ollama LLM on rule candidates (cached in llm_results.jsonl).
  5. Writes final CSVs FRESH (rebuild, not append) so re-runs stay idempotent.

Robots.txt bypass is approved by the user for this academic research project.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.config import Config
from crawler.downloader import Downloader
from crawler.extractor import Extractor
from crawler.storage import Storage
from crawler.oil_relevance import (
    classify_oil_relevance,
    merge_rule_and_llm,
    ollama_relevance_check,
)

RUN_NAME  = "edible_oil_adulteration_round_03_2026-06-23"
RUN_DIR   = ROOT / "data" / "runs" / RUN_NAME
CONFIG    = ROOT / "config" / "config_edible_oils_round3.yaml"
REL_DIR   = RUN_DIR / "mediacloud" / "outputs" / "oil_relevance"
META_CSV  = REL_DIR / "metadata_all_articles_review.csv"
QUEUE_CSV = REL_DIR / "crawl_queue.csv"
LLM_JSONL = REL_DIR / "llm_results.jsonl"
LLM_MODEL = "llama3.1:8b-instruct-q4_K_M"

# Tight phrase queries whose dropped results are worth crawling (exclude the
# 423-hit "adulterated food items" noise bucket).
TIGHT_PHRASES = {
    "fake oil", "edible oil traders", "seized adulterated food items",
    "edible oil samples", "substandard edible oil", "collected edible oil samples",
    "unfit edible oil", "mislabelled oils",
}

BASE_COLUMNS = [
    "article_id", "title", "source", "date", "url", "file_path",
    "query_family", "query_id", "rule_candidate", "oil_role", "final_label",
    "confidence", "reason", "evidence_phrase", "edible_oil_terms",
    "adulteration_action_terms", "negative_terms",
    "llm_label", "llm_confidence", "llm_reason", "llm_model",
]


def read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(p: Path, rows: list[dict], fieldnames: list[str]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def extract_phrase(query: str) -> str:
    m = re.match(r'\("(.+?)" AND', query or "")
    return m.group(1) if m else ""


def record_domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def db_urls_with_text(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as con:
        rows = con.execute(
            "SELECT url FROM articles WHERE article_text IS NOT NULL AND article_text != ''"
        ).fetchall()
    return {r[0] for r in rows if r[0]}


def db_articles_with_text(db_path: Path) -> list[dict]:
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM articles WHERE article_text IS NOT NULL AND article_text != ''"
        ).fetchall()
    return [dict(r) for r in rows]


def gather_targets(meta_rows: list[dict]) -> list[dict]:
    """Union of main crawl queue + tight phrase drops, deduped by URL."""
    queue = read_csv(QUEUE_CSV)
    targets: dict[str, dict] = {r["url"]: r for r in queue if r.get("url")}

    for r in meta_rows:
        if (
            r.get("query_family") == "phrase"
            and r.get("crawl_priority") == "drop"
            and extract_phrase(r.get("query_used", "")) in TIGHT_PHRASES
            and r.get("oil_role") != "non_food_oil"
        ):
            targets.setdefault(r["url"], r)
    return list(targets.values())


def load_llm_cache() -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if LLM_JSONL.exists():
        with LLM_JSONL.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("url"):
                    cache[row["url"]] = row
    return cache


def main() -> int:
    # --- Playwright + robots bypass MUST be set before Downloader() is built ---
    cfg = Config(CONFIG)
    crawl = cfg.raw.setdefault("crawl", {})
    crawl["respect_robots_txt"] = False
    crawl["use_playwright"] = True
    crawl["playwright_first"] = True
    crawl["timeout_seconds"] = 60
    crawl["delay_seconds"] = 2.0
    crawl["max_retries"] = 2

    db_path = cfg.path("db")
    storage = Storage(cfg)
    downloader = Downloader(cfg)
    extractor = Extractor(cfg)

    meta_rows = read_csv(META_CSV)
    meta_by_url = {r["url"]: r for r in meta_rows}
    targets = gather_targets(meta_rows)
    have_text = db_urls_with_text(db_path)
    to_crawl = [t for t in targets if t.get("url") not in have_text]

    print(f"Total targets: {len(targets)}  | already have text: {len(targets) - len(to_crawl)}  "
          f"| to crawl (Playwright): {len(to_crawl)}")

    crawled_ok = 0
    for i, t in enumerate(to_crawl, 1):
        url = t.get("url", "")
        print(f"  [{i}/{len(to_crawl)}] {url[:95]}", flush=True)
        result = downloader.download(url)
        status = result.get("status") or "failed"
        storage.mark_discovered_status(url, status)
        if status != "success":
            print(f"     -> {status}: {result.get('error_message','')[:60]}", flush=True)
            continue
        html = result.get("raw_html") or ""
        final_url = result.get("url") or url
        ext = extractor.extract(final_url, html, raw_html_path=result.get("raw_html_path"))
        if not ext.get("article_text"):
            print("     -> crawled but no text", flush=True)
            continue
        article = {
            "url": final_url,
            "canonical_url": ext.get("canonical_url") or final_url,
            "title": ext.get("title") or t.get("title") or "",
            "domain": record_domain(final_url),
            "source": t.get("source") or "",
            "publication_date": ext.get("publication_date") or t.get("date") or "",
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "query_used": t.get("query_used") or "",
            "discovery_method": "r3_supplemental_playwright",
            "raw_html_path": result.get("raw_html_path"),
            "cleaned_text_path": ext.get("cleaned_text_path"),
            "article_text": ext.get("article_text"),
            "extraction_status": ext.get("extraction_status"),
            "extraction_method": ext.get("extraction_method"),
            "word_count": ext.get("word_count") or 0,
        }
        if not storage.save_article(article):
            storage.update_article(url, {k: v for k, v in article.items() if k != "url"})
        crawled_ok += 1
        print(f"     -> ok ({article['word_count']} words)", flush=True)

    downloader.close()
    print(f"\nNewly crawled with text: {crawled_ok}")

    # --- Rule-classify ALL Round 3 articles with text (fresh rebuild) ---
    articles = db_articles_with_text(db_path)
    print(f"Total Round 3 articles with text: {len(articles)}")

    rule_rows = []
    for a in articles:
        url = a.get("url", "")
        meta = meta_by_url.get(url, {})
        title = a.get("title") or meta.get("title") or ""
        text = a.get("article_text") or ""
        dec = classify_oil_relevance(title=title, text=text, url=url)
        rule_rows.append({
            "article_id": meta.get("article_id", ""),
            "title": title,
            "source": a.get("source") or meta.get("source", ""),
            "date": a.get("publication_date") or meta.get("date", ""),
            "url": url,
            "file_path": a.get("cleaned_text_path") or "",
            "query_family": meta.get("query_family", ""),
            "query_id": meta.get("query_id", ""),
            **dec.to_dict(),
            "llm_label": "", "llm_confidence": "", "llm_reason": "", "llm_model": "",
        })
    print(f"Rule-based: {dict(Counter(r['final_label'] for r in rule_rows))}")

    # --- LLM on rule candidates (cached) ---
    art_by_url = {a["url"]: a for a in articles}
    llm_cache = load_llm_cache()
    candidates = [r for r in rule_rows if str(r.get("rule_candidate")) == "True"]
    print(f"LLM candidates: {len(candidates)} (cached: "
          f"{sum(1 for r in candidates if r['url'] in llm_cache)})")

    with LLM_JSONL.open("a", encoding="utf-8") as fh:
        for i, row in enumerate(candidates, 1):
            url = row["url"]
            if url in llm_cache:
                continue
            print(f"  [LLM {i}/{len(candidates)}] {url[:80]}", flush=True)
            article = art_by_url.get(url, {})
            try:
                llm = ollama_relevance_check(
                    title=row.get("title") or "",
                    text=article.get("article_text") or "",
                    url=url, model=LLM_MODEL,
                )
            except Exception as exc:
                llm = {"llm_label": "unclear", "llm_confidence": 0.0,
                       "llm_reason": f"LLM call failed: {exc}",
                       "evidence_phrase": "", "llm_model": LLM_MODEL}
            payload = {"url": url, **llm}
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
            fh.flush()
            llm_cache[url] = payload

    # --- Merge rule + LLM, write final CSVs fresh ---
    final_rows = []
    for row in rule_rows:
        url = row["url"]
        dec = classify_oil_relevance(title=row.get("title", ""), text="", url=url)
        dec.rule_candidate = str(row.get("rule_candidate")) == "True"
        dec.oil_role = row.get("oil_role") or dec.oil_role
        dec.final_label = row.get("final_label") or dec.final_label
        dec.confidence = float(row.get("confidence") or dec.confidence)
        dec.reason = row.get("reason") or dec.reason
        dec.evidence_phrase = row.get("evidence_phrase") or dec.evidence_phrase
        merged = {
            **{k: row.get(k, "") for k in BASE_COLUMNS if k in row},
            **merge_rule_and_llm(dec, llm_cache.get(url)),
        }
        final_rows.append(merged)

    cols = BASE_COLUMNS[:]
    for r in final_rows:
        for k in r:
            if k not in cols:
                cols.append(k)

    write_csv(REL_DIR / "all_articles_review.csv", final_rows, cols)
    write_csv(REL_DIR / "relevant_oil_articles.csv",
              [r for r in final_rows if r.get("final_label") == "relevant"], cols)
    write_csv(REL_DIR / "manual_review_articles.csv",
              [r for r in final_rows if r.get("final_label") == "manual_review"], cols)
    write_csv(REL_DIR / "irrelevant_articles.csv",
              [r for r in final_rows if r.get("final_label") == "irrelevant"], cols)

    counts = Counter(r.get("final_label") for r in final_rows)
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "r3_supplemental_crawl_v2",
        "targets": len(targets),
        "newly_crawled_with_text": crawled_ok,
        "total_articles_with_text": len(articles),
        "final_label_counts": dict(counts),
    }
    (REL_DIR / "r3_supplemental_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nDone.", json.dumps(summary, indent=2))
    storage.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
