"""
run_pipeline.py

The orchestrator. This file should stay THIN — it calls the functions in
pipeline/*.py in order, persists intermediate output at every stage, and
logs counts so you can see exactly where things go wrong. If you find
yourself writing actual filtering/extraction/query logic directly in
this file instead of calling out to a module, stop — that logic belongs
in the relevant module, not here. Keeping this file dumb is what makes
the pipeline debuggable: every stage's input and output sits on disk as
plain JSON, inspectable independent of re-running anything.

High-level flow per round:
    1. extract_keywords()       on this round's article pool
    2. filter_keywords()        -> clean keyword list (precision checkpoint #1)
    3. build_solr_query()       -> bounded query string(s)
    4. fetch()                  -> raw results, written to round_N_raw/
    5. score_article() per hit  -> precision checkpoint #2
    6. keep only passing articles -> written to round_N_filtered/
    7. passing articles become next round's article pool

After NUM_ROUNDS:
    8. scrape() full text for all kept articles across all rounds
    9. dedupe() the combined set
    10. write final dataset

Run this with `python run_pipeline.py` once every module below has a
real implementation — right now every pipeline/*.py function raises
NotImplementedError on purpose, so running this immediately will fail
loudly rather than silently doing nothing. Fill in extract_keywords.py
first (test it standalone on your 20 seeds before wiring it in here).
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from datetime import date

import config
from pipeline import (
    extract_keywords,
    filter_relevance,
    build_query,
    fetch_articles,
    scrape_fulltext,
    dedup,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOGS_DIR / "pipeline.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("milk_pipeline")


def load_seed_articles() -> list[dict]:
    """Load the manually curated seed articles from seeds/seed_articles.json."""
    path = config.SEEDS_DIR / "seed_articles.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: list[dict] | list[tuple], path: Path) -> None:
    """Persist any intermediate stage's output. Always called before
    moving to the next stage, never skipped — this is what lets you
    inspect any round's data without re-running the pipeline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_round(round_num: int, article_pool: list[dict], carried_keywords: list[str]) -> tuple[list[dict], list[str]]:
    """
    Run a single round of: extract -> filter keywords -> query -> fetch
    -> filter articles. Returns (newly_passing_articles, keywords_used)
    so the caller can decide what feeds the next round.

    NOTE: this function is intentionally not yet wired to call the
    NotImplementedError stubs with real arguments end-to-end — fill in
    each pipeline/*.py module first, test it standalone, THEN come back
    here and wire the real calls in. Trying to debug the whole loop
    before any single stage works in isolation is exactly the trap that
    made last time painful.
    """
    import importlib
    importlib.reload(config)
    
    logger.info(f"--- Round {round_num} starting with {len(article_pool)} articles in pool ---")

    raw_dir = config.DATA_DIR / f"round_{round_num}_raw"
    filtered_dir = config.DATA_DIR / f"round_{round_num}_filtered"

    # 1. Extract keyword candidates from this round's article pool.
    candidates = extract_keywords.extract_keywords(article_pool)

    # 2. Filter down to a clean, bounded keyword list (checkpoint #1).
    new_keywords = filter_relevance.filter_keywords(
        candidates,
        blocklist=config.KEYWORD_BLOCKLIST,
        top_n=config.TOP_N_KEYWORDS_PER_ROUND,
    )

    # Merge with any keywords carried over from a previous round.
    keywords = extract_keywords.merge_keyword_rounds(
        previous_keywords=carried_keywords,
        new_candidates=[(k, 0.0) for k in new_keywords],  # placeholder scores
        top_n=config.TOP_N_KEYWORDS_PER_ROUND,
    )
    logger.info(f"Round {round_num}: keywords = {keywords}")

    # 3. Build a bounded query.
    query = build_query.build_solr_query(keywords, max_terms=config.MAX_QUERY_TERMS)

    # 4. Fetch raw results — saved to disk BEFORE filtering.
    raw_results = fetch_articles.fetch(
        query=query,
        date_from=date(2021, 1, 1),  # Explicit date filter as requested
        date_to=None,
        max_results=config.MAX_RESULTS_PER_QUERY,
        timeout_seconds=config.REQUEST_TIMEOUT_SECONDS,
        max_retries=config.MAX_RETRIES,
        retry_backoff_seconds=config.RETRY_BACKOFF_SECONDS,
    )
    save_json(raw_results, raw_dir / "raw_results.json")
    logger.info(f"Round {round_num}: {len(raw_results)} raw results fetched")

    # 5-6. Score and filter (checkpoint #2).
    min_matches = (
        config.MIN_KEYWORD_MATCHES_ROUND1
        if round_num == 1
        else config.MIN_KEYWORD_MATCHES_LATER_ROUNDS
    )
    passing = []
    for article in raw_results:
        score = filter_relevance.score_article(article, keywords, min_matches, config.KEYWORD_BLOCKLIST)
        if score >= min_matches:
            passing.append(article)
    save_json(passing, filtered_dir / "filtered_results.json")
    logger.info(f"Round {round_num}: {len(passing)}/{len(raw_results)} passed automated relevance filter")

    # Manual filtering pause — type 'stop' to finalize the pipeline now,
    # or just press Enter to continue to the next round.
    print(f"\n{'='*50}")
    print(f"*** MANUAL FILTERING PAUSE — Round {round_num} ***")
    print(f"Review: {filtered_dir / 'filtered_results.json'}")
    print(f"Press Enter to run another round, or type 'stop' + Enter to finalize the dataset.")
    user_input = input("> ").strip().lower()
    stop_requested = user_input == "stop"

    # Reload passing after user edited it
    with open(filtered_dir / "filtered_results.json", "r", encoding="utf-8") as f:
        passing = json.load(f)

    logger.info(f"Round {round_num}: {len(passing)} articles kept after manual filter")

    return passing, keywords, stop_requested


def main() -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    seeds = load_seed_articles()
    save_json(seeds, config.DATA_DIR / "round_0_seeds" / "seeds.json")
    logger.info(f"Loaded {len(seeds)} seed articles")

    article_pool = seeds
    carried_keywords: list[str] = []
    all_found_articles: list[dict] = list(seeds)

    round_num = 1
    while True:
        article_pool, carried_keywords, stop_requested = run_round(round_num, article_pool, carried_keywords)
        all_found_articles.extend(article_pool)

        # Dedupe the full accumulated set after every round so duplicates
        # don't inflate keyword extraction in later rounds.
        all_found_articles = dedup.dedupe(all_found_articles)
        logger.info(f"Round {round_num}: {len(all_found_articles)} unique articles accumulated so far")

        if not article_pool:
            logger.warning(f"Round {round_num} found 0 passing articles — stopping early.")
            break
        if stop_requested:
            logger.info(f"User requested stop after round {round_num}. Finalizing dataset.")
            break
        round_num += 1

    # Scrape full text only for articles that survived filtering.
    urls = [a["url"] for a in all_found_articles if "url" in a]
    scraped = scrape_fulltext.scrape(urls)

    # Final dedup across all rounds combined.
    final_dataset = dedup.dedupe(scraped)
    save_json(final_dataset, config.DATA_DIR / "final_dataset.json")
    logger.info(f"Pipeline complete. Final dataset: {len(final_dataset)} articles.")


if __name__ == "__main__":
    main()
