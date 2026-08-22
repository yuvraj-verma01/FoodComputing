"""Run MediaCloud URL discovery for ghee Round 1.

This is the ghee-specific version of the edible-oil discovery step. It uses the
approved ghee query plan as-is and intentionally applies no hidden NOT terms or
metadata exclusion filter.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.config import Config
from crawler.discovery.mediacloud import MediaCloudDiscovery
from crawler.review_dedupe import load_reviewed_url_keys, split_new_review_rows
from crawler.storage import Storage


DEFAULT_RUN_DIR = ROOT / "data" / "runs" / "ghee_adulteration_round_01_2026-06-30"
DEFAULT_CONFIG = ROOT / "config" / "config_ghee_round1.yaml"
DEFAULT_QUERY_PLAN = DEFAULT_RUN_DIR / "proposed_mediacloud_ghee_round1_seed_queries.csv"

PRODUCT_TERMS = {
    "ghee",
    "cow ghee",
    "desi ghee",
    "pure ghee",
    "loose ghee",
    "fake ghee",
    "fake cow ghee",
    "adulterated ghee",
    "suspected adulterated ghee",
    "vegetable ghee",
    "ghee racket",
    "ghee racket busted",
}

SIGNAL_TERMS = {
    "adulterated",
    "fake",
    "seized",
    "raid",
    "food safety",
    "fda",
    "fssai",
    "vanaspati",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--query-plan", type=Path, default=DEFAULT_QUERY_PLAN)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument(
        "--include-reviewed-urls",
        action="store_true",
        help="Keep URLs already human-marked in previous rounds in review outputs.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cfg = Config(args.config)
    query_plan = read_query_plan(args.query_plan)
    storage = Storage(cfg)

    try:
        mc = MediaCloudDiscovery(cfg)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    stats: dict[str, Counter[str]] = defaultdict(Counter)
    client = mc._get_client()

    print(f"Indian MediaCloud collections: {len(mc.collection_ids)}")
    print(f"Date range: {cfg.date_start} to {cfg.date_end}")
    print(f"Running {len(query_plan)} approved ghee MediaCloud queries")

    for index, query_row in enumerate(query_plan, start=1):
        query = query_row["query"]
        query_id = query_row["query_id"]
        family = query_row["query_family"]
        print(f"[{index}/{len(query_plan)}] {family}: {query_id}")
        started = time.time()
        for rec in mc._search(client, query):
            stats[query]["raw_records_seen"] += 1
            rec["discovery_method"] = f"mediacloud_{family}"
            if storage.save_discovered(rec):
                stats[query]["saved_new_urls"] += 1
            else:
                stats[query]["duplicates_in_run"] += 1
        elapsed = time.time() - started
        print(
            "  raw={raw} saved={saved} duplicates={dupes} ({elapsed:.1f}s)".format(
                raw=stats[query]["raw_records_seen"],
                saved=stats[query]["saved_new_urls"],
                dupes=stats[query]["duplicates_in_run"],
                elapsed=elapsed,
            )
        )
        time.sleep(mc.delay)

    output_dir = cfg.path("outputs")
    discovered_rows = read_discovered_rows(cfg.path("db"))
    write_review_outputs(
        output_dir=output_dir,
        db_path=cfg.path("db"),
        discovered_rows=discovered_rows,
        query_plan=query_plan,
        stats=stats,
        include_reviewed_urls=args.include_reviewed_urls,
    )
    storage.close()
    mc.close()

    print(f"Discovered unique URLs saved: {len(discovered_rows)}")
    print(f"Wrote review CSVs under: {output_dir}")
    return 0


def read_query_plan(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing query plan: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Query plan is empty: {path}")
    required = {"query", "query_id", "query_family"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"Query plan is missing columns: {sorted(missing)}")
    return rows


def read_discovered_rows(db_path: Path) -> list[dict[str, str]]:
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


def write_review_outputs(
    output_dir: Path,
    db_path: Path,
    discovered_rows: list[dict[str, str]],
    query_plan: list[dict[str, str]],
    stats: dict[str, Counter[str]],
    include_reviewed_urls: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    query_lookup = {row["query"]: row for row in query_plan}

    review_rows = []
    label_counts: Counter[str] = Counter()
    query_saved_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for row in discovered_rows:
        query = row.get("query_used") or ""
        query_row = query_lookup.get(query, {})
        text_for_screen = " ".join(
            [
                row.get("title_snippet") or "",
                row.get("url") or "",
                row.get("source") or "",
                row.get("domain") or "",
            ]
        )
        product_matches = matching_terms(text_for_screen, PRODUCT_TERMS)
        signal_matches = matching_terms(text_for_screen, SIGNAL_TERMS)
        label = title_screen_label(product_matches, signal_matches)

        label_counts[label] += 1
        query_saved_counts[query] += 1
        domain_counts[row.get("domain") or ""] += 1
        status_counts[row.get("status") or ""] += 1

        review_rows.append(
            {
                "review_keep": "",
                "title_screen_label": label,
                "query_family": query_row.get("query_family", "not_in_plan"),
                "query_id": query_row.get("query_id", ""),
                "title_url_product_terms": "; ".join(product_matches[:8]),
                "title_url_signal_terms": "; ".join(signal_matches[:8]),
                "published_date": row.get("published_date") or "",
                "domain": row.get("domain") or "",
                "source": row.get("source") or "",
                "title_snippet": row.get("title_snippet") or "",
                "query_used": query,
                "status": row.get("status") or "",
                "url": row.get("url") or "",
            }
        )

    previously_reviewed_rows: list[dict[str, str]] = []
    reviewed_url_key_count = 0
    if not include_reviewed_urls:
        reviewed_url_keys = load_reviewed_url_keys()
        reviewed_url_key_count = len(reviewed_url_keys)
        review_rows, previously_reviewed_rows = split_new_review_rows(review_rows, reviewed_url_keys)

    query_count_rows = []
    for row in query_plan:
        query = row["query"]
        query_count_rows.append(
            {
                "query_number": row.get("query_number", ""),
                "query_id": row.get("query_id", ""),
                "query_family": row.get("query_family", ""),
                "query": query,
                "raw_records_seen": stats[query]["raw_records_seen"],
                "saved_new_urls": stats[query]["saved_new_urls"],
                "saved_urls_in_db": query_saved_counts[query],
                "duplicates_in_run": stats[query]["duplicates_in_run"],
                "product_groups": row.get("product_groups", ""),
                "signal_mode": row.get("signal_mode", ""),
                "date_start": row.get("date_start", ""),
                "date_end": row.get("date_end", ""),
                "breadth": row.get("breadth", ""),
                "reason": row.get("reason", ""),
            }
        )

    dates = [row.get("published_date") for row in discovered_rows if row.get("published_date")]
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(DEFAULT_RUN_DIR),
        "db_path": str(db_path),
        "total_discovered_urls": len(discovered_rows),
        "review_rows_written": len(review_rows),
        "previously_reviewed_urls_excluded": len(previously_reviewed_rows),
        "reviewed_url_key_count": reviewed_url_key_count,
        "include_reviewed_urls": include_reviewed_urls,
        "planned_query_count": len(query_plan),
        "query_family_counts": dict(Counter(row.get("query_family", "") for row in review_rows)),
        "status_counts": dict(sorted(status_counts.items())),
        "queries_with_saved_urls": sum(1 for count in query_saved_counts.values() if count > 0),
        "distinct_domains": len(domain_counts),
        "published_date_min": min(dates) if dates else "",
        "published_date_max": max(dates) if dates else "",
        "title_screen_counts": dict(sorted(label_counts.items())),
        "top_domains": [
            {"domain": domain, "count": count}
            for domain, count in domain_counts.most_common(20)
        ],
        "notes": [
            "Ghee Round 1 URL discovery only; article text has not been crawled by this step.",
            "Only human-approved ghee query terms were used.",
            "No hidden NOT/exclusion terms or metadata exclusion filters were applied.",
            "Title screen labels use title, URL, source, and domain metadata only.",
        ],
    }

    columns = [
        "review_keep",
        "title_screen_label",
        "query_family",
        "query_id",
        "title_url_product_terms",
        "title_url_signal_terms",
        "published_date",
        "domain",
        "source",
        "title_snippet",
        "query_used",
        "status",
        "url",
    ]
    write_csv(output_dir / "discovery_url_review.csv", review_rows, columns)
    write_csv(output_dir / "discovery_previously_reviewed_urls.csv", previously_reviewed_rows, columns)
    write_csv(output_dir / "discovery_query_counts.csv", query_count_rows, list(query_count_rows[0].keys()))
    (output_dir / "discovery_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize(text: str | None) -> str:
    import re

    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return f" {re.sub(r'\\s+', ' ', text).strip()} "


def matching_terms(text: str, terms: set[str]) -> list[str]:
    normalized = normalize(text)
    matches = []
    for term in sorted(terms, key=lambda item: (-len(item), item)):
        normalized_term = normalize(term).strip()
        if f" {normalized_term} " in normalized:
            matches.append(term)
    return matches


def title_screen_label(product_matches: list[str], signal_matches: list[str]) -> str:
    if product_matches and signal_matches:
        return "strong_title_match"
    if product_matches:
        return "ghee_context_only_in_title"
    if signal_matches:
        return "broad_food_safety_title"
    return "weak_or_body_only_match"


if __name__ == "__main__":
    raise SystemExit(main())
