"""Crawl every metadata-dropped URL from all rounds, score with best model, save results.

Checkpoints after each URL so it can be interrupted and resumed.
Usage: python scripts/rescreen_all_dropped.py
"""
from __future__ import annotations
import csv, json, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import joblib
from crawler.config import Config
from crawler.downloader import Downloader
from crawler.extractor import Extractor
from src.model_training.build_text_representations import build_single

# ── Paths ─────────────────────────────────────────────────────────────────────
MASTER_CSV   = ROOT / "reports/master_corpus/master_all_articles.csv"
MODEL_PATH   = ROOT / "reports/model_training/trained_models/best_model.joblib"
MODEL_CFG    = ROOT / "reports/model_training/trained_models/best_model_config.json"
RUN_CFG      = ROOT / "config/config_edible_oils_round3.yaml"
OUT_DIR      = ROOT / "reports/rescreen"
CHECKPOINT   = OUT_DIR / "_crawl_checkpoint.json"
FINAL_CSV    = OUT_DIR / "rescreen_all_dropped.csv"

R1_DISC = ROOT / "data/runs/edible_oils_boolean_title_proximity_2026-06-22/mediacloud/outputs/discovery_url_review.csv"
R2_META = ROOT / "data/runs/edible_oil_adulteration_round_02_2026-06-23/mediacloud/outputs/oil_relevance/metadata_all_articles_review.csv"
R3_META = ROOT / "data/runs/edible_oil_adulteration_round_03_2026-06-23/mediacloud/outputs/oil_relevance/metadata_all_articles_review.csv"

HIGH_RECALL_T    = 0.35
HIGH_PRECISION_T = 0.65


def read_csv(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def collect_candidates(master_urls: set) -> list[dict]:
    """Gather all dropped/unreviewed URLs from all rounds, dedup against master."""
    pool: dict[str, dict] = {}

    # Round 2 & 3 — explicit crawl_priority=drop
    for path, rnd in [(R2_META, 2), (R3_META, 3)]:
        for r in read_csv(path):
            if r.get("crawl_priority") != "drop":
                continue
            url = r.get("url", "").strip()
            if url and url not in master_urls and url not in pool:
                pool[url] = {
                    "url":          url,
                    "title":        r.get("title", ""),
                    "source":       r.get("source", ""),
                    "date":         r.get("date", ""),
                    "query_family": r.get("query_family", ""),
                    "round":        str(rnd),
                }

    # Round 1 — all discovery URLs not already in master
    for r in read_csv(R1_DISC):
        url = r.get("url", "").strip()
        if url and url not in master_urls and url not in pool:
            pool[url] = {
                "url":          url,
                "title":        r.get("title_snippet", ""),
                "source":       r.get("source", ""),
                "date":         r.get("published_date", ""),
                "query_family": r.get("query_family", ""),
                "round":        "1",
            }

    return list(pool.values())


def load_checkpoint() -> dict[str, dict]:
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return {}


def save_checkpoint(done: dict[str, dict]) -> None:
    CHECKPOINT.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")


def bucket(prob: float) -> str:
    if prob >= HIGH_PRECISION_T:
        return "candidate_relevant"
    if prob >= HIGH_RECALL_T:
        return "manual_review"
    return "candidate_irrelevant"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load master corpus URLs to skip
    master_rows = read_csv(MASTER_CSV)
    master_urls = {r["url"].strip() for r in master_rows if r.get("url")}
    print(f"Master corpus: {len(master_rows)} rows, {len(master_urls)} unique URLs")

    # Collect all dropped candidates
    candidates = collect_candidates(master_urls)
    rounds = Counter(c["round"] for c in candidates)
    print(f"Candidates to crawl: {len(candidates)}  (by round: {dict(rounds)})")

    # Load checkpoint (already-crawled URLs)
    done = load_checkpoint()
    remaining = [c for c in candidates if c["url"] not in done]
    print(f"Already done: {len(done)}, remaining: {len(remaining)}")

    # Set up crawler
    cfg = Config(RUN_CFG)
    crawl_cfg = cfg.raw.setdefault("crawl", {})
    crawl_cfg["respect_robots_txt"] = False
    crawl_cfg["use_playwright"]     = True
    crawl_cfg["playwright_first"]   = True
    crawl_cfg["timeout_seconds"]    = 45
    crawl_cfg["delay_seconds"]      = 1.5
    crawl_cfg["max_retries"]        = 1
    downloader = Downloader(cfg)
    extractor  = Extractor(cfg)

    # Load best model
    model_cfg  = json.loads(MODEL_CFG.read_text(encoding="utf-8"))
    repr_name  = model_cfg.get("representation", "title_plus_keyword_windows")
    pipeline   = joblib.load(MODEL_PATH)
    print(f"Model: {model_cfg.get('model_name')} × {repr_name}")
    print(f"\nStarting crawl of {len(remaining)} URLs ...\n")

    for i, cand in enumerate(remaining, 1):
        url   = cand["url"]
        title = cand["title"]
        print(f"[{i+len(done)}/{len(candidates)}] {url[:90]}", flush=True)

        result = downloader.download(url)
        status = result.get("status", "failed")

        if status != "success":
            record = {**cand, "crawl_status": status,
                      "article_text": "", "word_count": 0,
                      "prob": None, "bucket": "crawl_failed"}
        else:
            html      = result.get("raw_html") or ""
            final_url = result.get("url") or url
            ext       = extractor.extract(final_url, html,
                                          raw_html_path=result.get("raw_html_path"))
            text = ext.get("article_text") or ""
            wc   = ext.get("word_count") or 0

            if text:
                rep  = build_single(title, text, repr_name)
                prob = float(pipeline.predict_proba([rep])[0, 1])
                bkt  = bucket(prob)
                print(f"  -> {wc}w  prob={prob:.3f}  [{bkt}]", flush=True)
            else:
                prob, bkt = None, "no_text"
                print(f"  -> crawled, no text", flush=True)

            record = {**cand, "crawl_status": "success",
                      "article_text": text, "word_count": wc,
                      "prob": prob, "bucket": bkt}

        done[url] = record
        # Checkpoint every 10 URLs
        if i % 10 == 0:
            save_checkpoint(done)

    downloader.close()
    save_checkpoint(done)

    # Write final CSV
    fieldnames = ["round", "url", "title", "source", "date", "query_family",
                  "crawl_status", "word_count", "prob", "bucket", "article_text"]
    all_records = sorted(done.values(),
                         key=lambda r: (r.get("prob") or 0), reverse=True)

    with FINAL_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_records)

    # Summary
    bkt_counts = Counter(r["bucket"] for r in done.values())
    crawled    = sum(1 for r in done.values() if r["crawl_status"] == "success")
    has_text   = sum(1 for r in done.values() if r.get("article_text"))
    print(f"\n{'='*55}")
    print(f"Total URLs processed : {len(done)}")
    print(f"Crawled successfully  : {crawled}")
    print(f"Got article text      : {has_text}")
    print(f"Buckets: {dict(bkt_counts)}")
    print(f"Output: {FINAL_CSV}")
    print(f"{'='*55}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
