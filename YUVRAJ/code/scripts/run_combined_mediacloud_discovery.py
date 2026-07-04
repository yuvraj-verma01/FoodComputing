"""Run combined Media Cloud discovery and prepare review outputs.

This intentionally performs URL discovery only. It does not crawl article text.
The run includes Boolean, title-only Boolean, and proximity query families.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import shutil
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


DEFAULT_RUN_DIR = ROOT / "data" / "runs" / "edible_oil_adulteration_round_02_2026-06-23"
DEFAULT_CONFIG = ROOT / "config" / "config_edible_oils_combined.yaml"
DEFAULT_QUERY_PLAN = DEFAULT_RUN_DIR / "proposed_mediacloud_combined_seed_queries.csv"
DEFAULT_BASELINE_RUN = ROOT / "data" / "runs" / "edible_oils_boolean_2026-06-21"

HARD_EXCLUSION_TERMS = [
    "ghee",
    "vanaspati",
    "Indonesia",
    "Joko Widodo",
    "rupiah",
    "rupiah per litre",
    "oil exports",
    "export ban",
    "futures",
    "derivative",
    "derivatives",
    "SEBI",
    "stock market",
    "domestic market",
    "solvent extractors association",
    "million tonnes",
    "million tonne",
    "sports drinks",
    "reused cooking oil",
    "biodiesel",
    "bio-diesel",
    "soda",
    "diesel",
    "heroin",
    "hidden in cooking oil cargo",
]

HARD_EXCLUSION_RE = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in HARD_EXCLUSION_TERMS) + r")\b",
    re.IGNORECASE,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--query-plan", type=Path, default=DEFAULT_QUERY_PLAN)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--baseline-run-dir", type=Path, default=DEFAULT_BASELINE_RUN)
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete this run's mediacloud output folder before discovery.",
    )
    parser.add_argument(
        "--include-reviewed-urls",
        action="store_true",
        help="Keep URLs already human-marked in previous rounds in review outputs.",
    )
    args = parser.parse_args()

    setup_logging()
    if args.fresh:
        remove_mediacloud_outputs(args.run_dir)

    cfg = Config(args.config)
    storage = Storage(cfg)
    query_plan = read_query_plan(args.query_plan)
    baseline_urls = load_baseline_urls(args.baseline_run_dir)

    try:
        mc = MediaCloudDiscovery(cfg)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    stats: dict[str, Counter[str]] = defaultdict(Counter)
    excluded_rows: list[dict[str, str]] = []
    client = mc._get_client()

    print(f"Running {len(query_plan)} Media Cloud queries")
    for index, query_row in enumerate(query_plan, start=1):
        query = query_row["query"]
        query_id = query_row["query_id"]
        family = query_row["query_family"]
        print(f"[{index}/{len(query_plan)}] {family}: {query_id}")
        started = time.time()
        for rec in mc._search(client, query):
            stats[query]["raw_records_seen"] += 1
            if has_hard_exclusion(rec):
                stats[query]["blocked_hard_exclusion"] += 1
                excluded_rows.append(excluded_record(query_row, rec))
                continue
            rec["discovery_method"] = f"mediacloud_{family}"
            if storage.save_discovered(rec):
                stats[query]["saved_new_urls"] += 1
            else:
                stats[query]["duplicates_in_run"] += 1
        elapsed = time.time() - started
        print(
            "  raw={raw} saved={saved} duplicates={dupes} blocked={blocked} ({elapsed:.1f}s)".format(
                raw=stats[query]["raw_records_seen"],
                saved=stats[query]["saved_new_urls"],
                dupes=stats[query]["duplicates_in_run"],
                blocked=stats[query]["blocked_hard_exclusion"],
                elapsed=elapsed,
            )
        )
        time.sleep(mc.delay)

    output_dir = cfg.path("outputs")
    discovered_rows = read_discovered_rows(cfg.path("db"))
    write_excluded_rows(output_dir / "excluded_hard_not_terms.csv", excluded_rows)
    write_review_outputs(
        output_dir=output_dir,
        db_path=cfg.path("db"),
        discovered_rows=discovered_rows,
        query_plan=query_plan,
        stats=stats,
        baseline_urls=baseline_urls,
        include_reviewed_urls=args.include_reviewed_urls,
    )
    storage.close()
    mc.close()
    print(f"Discovered URLs saved: {len(discovered_rows)}")
    print(f"Wrote review CSVs under: {output_dir}")
    return 0


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def remove_mediacloud_outputs(run_dir: Path) -> None:
    target = (run_dir / "mediacloud").resolve()
    allowed_root = (ROOT / "data" / "runs").resolve()
    if allowed_root not in target.parents:
        raise ValueError(f"Refusing to delete outside data/runs: {target}")
    if target.exists():
        shutil.rmtree(target)


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


def has_hard_exclusion(record: dict[str, str]) -> bool:
    text = " ".join(
        [
            record.get("title_snippet") or "",
            record.get("url") or "",
            record.get("source") or "",
            record.get("domain") or "",
        ]
    )
    return bool(HARD_EXCLUSION_RE.search(text))


def excluded_record(query_row: dict[str, str], rec: dict[str, str]) -> dict[str, str]:
    return {
        "query_id": query_row.get("query_id", ""),
        "query_family": query_row.get("query_family", ""),
        "published_date": rec.get("published_date") or "",
        "domain": rec.get("domain") or "",
        "source": rec.get("source") or "",
        "title_snippet": rec.get("title_snippet") or "",
        "url": rec.get("url") or "",
        "query_used": query_row.get("query", ""),
    }


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


def load_baseline_urls(run_dir: Path) -> set[str]:
    db_path = run_dir / "mediacloud" / "outputs" / "articles.db"
    if db_path.exists():
        with sqlite3.connect(db_path) as con:
            rows = con.execute("SELECT url FROM discovered_urls").fetchall()
        return {row[0] for row in rows if row and row[0]}

    jsonl_path = run_dir / "mediacloud" / "outputs" / "discovered_urls.jsonl"
    if not jsonl_path.exists():
        return set()

    urls = set()
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = rec.get("url")
            if url:
                urls.add(url)
    return urls


def write_review_outputs(
    output_dir: Path,
    db_path: Path,
    discovered_rows: list[dict[str, str]],
    query_plan: list[dict[str, str]],
    stats: dict[str, Counter[str]],
    baseline_urls: set[str],
    include_reviewed_urls: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    query_lookup = {row["query"]: row for row in query_plan}
    product_terms = sorted(PRODUCT_TERMS, key=lambda item: (-len(item), item))
    signal_terms = sorted(SIGNAL_TERMS, key=lambda item: (-len(item), item))

    review_rows = []
    label_counts: Counter[str] = Counter()
    query_saved_counts: Counter[str] = Counter()
    query_baseline_overlap_counts: Counter[str] = Counter()
    query_novel_counts: Counter[str] = Counter()
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
        product_matches = matching_terms(text_for_screen, product_terms)
        signal_matches = matching_terms(text_for_screen, signal_terms)
        label = title_screen_label(product_matches, signal_matches)
        novelty = "already_in_boolean_run" if row.get("url") in baseline_urls else "new_vs_boolean_run"

        label_counts[label] += 1
        query_saved_counts[query] += 1
        domain_counts[row.get("domain") or ""] += 1
        status_counts[row.get("status") or ""] += 1
        if novelty == "already_in_boolean_run":
            query_baseline_overlap_counts[query] += 1
        else:
            query_novel_counts[query] += 1

        review_rows.append(
            {
                "review_keep": "",
                "title_screen_label": label,
                "novelty_vs_boolean": novelty,
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
                "template_type": row.get("query_family", ""),
                "query": query,
                "raw_records_seen": stats[query]["raw_records_seen"],
                "saved_new_urls": stats[query]["saved_new_urls"],
                "saved_urls_in_db": query_saved_counts[query],
                "duplicates_in_run": stats[query]["duplicates_in_run"],
                "blocked_hard_exclusion": stats[query]["blocked_hard_exclusion"],
                "already_in_boolean_run_saved_urls": query_baseline_overlap_counts[query],
                "new_vs_boolean_run_saved_urls": query_novel_counts[query],
                "product_term": row.get("product_groups", ""),
                "fraud_term": row.get("signal_mode", ""),
                "enforcement_term": "",
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
        "query_family_counts": dict(
            Counter(row.get("query_family", "") for row in review_rows)
        ),
        "novelty_counts": dict(Counter(row.get("novelty_vs_boolean", "") for row in review_rows)),
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
            "This is URL discovery only; no article text has been crawled.",
            "All queries include the human-approved Round 1 hard NOT exclusion block.",
            "A metadata post-filter also removes records that still expose those hard exclusions in title/source/URL fields.",
            "Title screen labels use title, URL, source, and domain metadata only.",
        ],
    }

    write_csv(
        output_dir / "discovery_url_review.csv",
        review_rows,
        [
            "review_keep",
            "title_screen_label",
            "novelty_vs_boolean",
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
        ],
    )
    write_csv(
        output_dir / "discovery_previously_reviewed_urls.csv",
        previously_reviewed_rows,
        [
            "review_keep",
            "title_screen_label",
            "novelty_vs_boolean",
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
        ],
    )
    write_csv(
        output_dir / "discovery_query_counts.csv",
        query_count_rows,
        list(query_count_rows[0].keys()) if query_count_rows else [],
    )
    (output_dir / "discovery_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_excluded_rows(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "query_id",
        "query_family",
        "published_date",
        "domain",
        "source",
        "title_snippet",
        "url",
        "query_used",
    ]
    write_csv(path, rows, fieldnames)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


PRODUCT_TERMS = {
    "oil",
    "oils",
    "edible oil",
    "cooking oil",
    "vegetable oil",
    "refined oil",
    "loose oil",
    "loose edible oil",
    "mustard oil",
    "palm oil",
    "soybean oil",
    "sunflower oil",
    "groundnut oil",
    "coconut oil",
    "rice bran oil",
    "cottonseed oil",
    "sesame oil",
    "olive oil",
    "rapeseed-mustard oil",
}

SIGNAL_TERMS = {
    "adulteration",
    "adulterated",
    "contamination",
    "contaminated",
    "misbranding",
    "misbranded",
    "substandard",
    "spurious",
    "fake",
    "counterfeit",
    "unsafe",
    "rancid",
    "reused oil",
    "recycled oil",
    "mixed with",
    "fssai",
    "fsda",
    "fda",
    "food safety",
    "food safety department",
    "food safety officer",
    "raid",
    "raids",
    "raided",
    "seized",
    "seizure",
    "sample",
    "samples",
    "lab test",
    "quality test",
    "prosecution",
    "penalty",
    "fine",
    "ban",
    "banned",
    "license suspended",
    "licence suspended",
    "shop sealed",
    "warehouse",
    "godown",
    "arrested",
    "crackdown",
    "inspection",
}


def normalize(text: str | None) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return f" {re.sub(r'\\s+', ' ', text).strip()} "


def matching_terms(text: str, terms: list[str]) -> list[str]:
    normalized = normalize(text)
    matches = []
    for term in terms:
        normalized_term = normalize(term).strip()
        if f" {normalized_term} " in normalized:
            matches.append(term)
    return matches


def title_screen_label(product_matches: list[str], signal_matches: list[str]) -> str:
    if product_matches and signal_matches:
        return "strong_title_match"
    if product_matches:
        return "oil_context_only_in_title"
    if signal_matches:
        return "broad_food_safety_title"
    return "weak_or_body_only_match"


if __name__ == "__main__":
    raise SystemExit(main())
