"""Summarize Media Cloud discovery output for review.

This script reads the URL queue produced by ``mc-discover`` and creates small
review files. It does not crawl article text or change URL statuses.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = ROOT / "data" / "runs" / "edible_oils_from_sample_2026-06-21"

PRODUCT_FALLBACKS = {
    "oil",
    "oils",
    "edible oil",
    "cooking oil",
    "mustard oil",
    "coconut oil",
    "soybean oil",
    "vegetable oil",
    "groundnut oil",
    "palm oil",
    "olive oil",
    "ghee",
    "vanaspati",
}

SIGNAL_FALLBACKS = {
    "adulteration",
    "adulterated",
    "substandard",
    "fake",
    "spurious",
    "misbranded",
    "contaminated",
    "unsafe",
    "fssai",
    "fsda",
    "fda",
    "food safety",
    "raid",
    "raids",
    "seized",
    "seizure",
    "sample",
    "samples",
    "test",
    "inspection",
    "banned",
    "ban",
    "fine",
    "penalty",
}


def normalize(text: str | None) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return f" {re.sub(r'\\s+', ' ', text).strip()} "


def load_terms(path: Path) -> tuple[set[str], set[str]]:
    product_terms = set(PRODUCT_FALLBACKS)
    signal_terms = set(SIGNAL_FALLBACKS)
    if not path.exists():
        return product_terms, signal_terms

    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            term = (row.get("term") or "").strip().lower()
            category = (row.get("category") or "").strip().lower()
            if not term:
                continue
            if category == "product":
                product_terms.add(term)
            elif category in {"fraud", "enforcement"}:
                signal_terms.add(term)
    return product_terms, signal_terms


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
        return "oil_context_only_in_title"
    if signal_matches:
        return "broad_food_safety_title"
    return "weak_or_body_only_match"


def read_discovered_rows(db_path: Path) -> list[dict[str, str]]:
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            select id, url, discovery_method, query_used, discovered_at,
                   title_snippet, source, domain, published_date, status
            from discovered_urls
            order by published_date desc, id asc
            """
        ).fetchall()
    return [dict(row) for row in rows]


def count_articles(db_path: Path) -> int:
    with sqlite3.connect(db_path) as con:
        return int(con.execute("select count(*) from articles").fetchone()[0])


def read_query_plan(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()

    run_dir = args.run_dir
    output_dir = run_dir / "mediacloud" / "outputs"
    db_path = output_dir / "articles.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Missing discovery database: {db_path}")

    rows = read_discovered_rows(db_path)
    article_count = count_articles(db_path)
    query_plan = read_query_plan(run_dir / "proposed_mediacloud_seed_queries.csv")
    product_terms, signal_terms = load_terms(run_dir / "final_keyword_bank.csv")

    reviewed_rows = []
    label_counts: Counter[str] = Counter()
    query_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for row in rows:
        screen_text = " ".join(
            [
                row.get("title_snippet") or "",
                row.get("url") or "",
                row.get("source") or "",
                row.get("domain") or "",
            ]
        )
        product_matches = matching_terms(screen_text, product_terms)
        signal_matches = matching_terms(screen_text, signal_terms)
        label = title_screen_label(product_matches, signal_matches)

        label_counts[label] += 1
        query_counts[row.get("query_used") or ""] += 1
        domain_counts[row.get("domain") or ""] += 1
        status_counts[row.get("status") or ""] += 1

        reviewed_rows.append(
            {
                "review_keep": "",
                "title_screen_label": label,
                "title_url_product_terms": "; ".join(product_matches[:8]),
                "title_url_signal_terms": "; ".join(signal_matches[:8]),
                "published_date": row.get("published_date") or "",
                "domain": row.get("domain") or "",
                "source": row.get("source") or "",
                "title_snippet": row.get("title_snippet") or "",
                "query_used": row.get("query_used") or "",
                "status": row.get("status") or "",
                "url": row.get("url") or "",
            }
        )

    query_count_rows = []
    planned_queries = [row.get("query") or "" for row in query_plan]
    planned_query_set = set(planned_queries)
    for index, query in enumerate(planned_queries, start=1):
        plan_row = query_plan[index - 1]
        query_count_rows.append(
            {
                "query_number": index,
                "query": query,
                "saved_new_urls": query_counts.get(query, 0),
                "template_type": plan_row.get("template_type") or "",
                "product_term": plan_row.get("product_term") or "",
                "fraud_term": plan_row.get("fraud_term") or "",
                "enforcement_term": plan_row.get("enforcement_term") or "",
                "date_start": plan_row.get("date_start") or "",
                "date_end": plan_row.get("date_end") or "",
                "breadth": plan_row.get("breadth") or "",
            }
        )
    for query, count in sorted(query_counts.items()):
        if query not in planned_query_set:
            query_count_rows.append(
                {
                    "query_number": "",
                    "query": query,
                    "saved_new_urls": count,
                    "template_type": "not_in_query_plan",
                    "product_term": "",
                    "fraud_term": "",
                    "enforcement_term": "",
                    "date_start": "",
                    "date_end": "",
                    "breadth": "",
                }
            )

    dates = [row.get("published_date") for row in rows if row.get("published_date")]
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "db_path": str(db_path),
        "total_discovered_urls": len(rows),
        "articles_table_rows": article_count,
        "status_counts": dict(sorted(status_counts.items())),
        "planned_query_count": len(planned_queries),
        "queries_with_saved_urls": sum(1 for count in query_counts.values() if count > 0),
        "distinct_domains": len(domain_counts),
        "published_date_min": min(dates) if dates else "",
        "published_date_max": max(dates) if dates else "",
        "title_screen_counts": dict(sorted(label_counts.items())),
        "top_domains": [
            {"domain": domain, "count": count}
            for domain, count in domain_counts.most_common(20)
        ],
        "notes": [
            "Title screen is based only on title, URL, source, and domain metadata.",
            "weak_or_body_only_match can still be relevant if Media Cloud matched terms in article body.",
            "No article text has been crawled by this summary script.",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "discovery_query_counts.csv",
        query_count_rows,
        [
            "query_number",
            "query",
            "saved_new_urls",
            "template_type",
            "product_term",
            "fraud_term",
            "enforcement_term",
            "date_start",
            "date_end",
            "breadth",
        ],
    )
    write_csv(
        output_dir / "discovery_url_review.csv",
        reviewed_rows,
        [
            "review_keep",
            "title_screen_label",
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
    (output_dir / "discovery_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Wrote {output_dir / 'discovery_summary.json'}")
    print(f"Wrote {output_dir / 'discovery_query_counts.csv'}")
    print(f"Wrote {output_dir / 'discovery_url_review.csv'}")
    print(f"Discovered URLs: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
