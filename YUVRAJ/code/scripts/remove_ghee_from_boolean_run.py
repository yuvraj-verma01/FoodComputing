"""Remove ghee/vanaspati discoveries from the active Boolean edible-oil run.

The script keeps the cleanup auditable by writing every removed record to CSV
and JSONL before deleting it from the SQLite URL queue.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = ROOT / "data" / "runs" / "edible_oils_boolean_2026-06-21"
BLOCKED_RE = re.compile(r"\b(ghee|vanaspati)\b", re.IGNORECASE)
DISCOVERED_FIELDS = [
    "url",
    "discovery_method",
    "query_used",
    "discovered_at",
    "title_snippet",
    "source",
    "domain",
    "published_date",
    "status",
]


def row_text(row: dict[str, object]) -> str:
    return " ".join(
        str(row.get(field) or "")
        for field in ("url", "query_used", "title_snippet", "source", "domain")
    )


def is_blocked(row: dict[str, object]) -> bool:
    return bool(BLOCKED_RE.search(row_text(row)))


def fetch_rows(db_path: Path) -> list[dict[str, object]]:
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            select id, url, discovery_method, query_used, discovered_at,
                   title_snippet, source, domain, published_date, status
            from discovered_urls
            order by id asc
            """
        ).fetchall()
    return [dict(row) for row in rows]


def write_removed_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "removed_reason",
        "id",
        "published_date",
        "domain",
        "source",
        "title_snippet",
        "query_used",
        "status",
        "url",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "removed_reason": "contains whole-word ghee or vanaspati",
                    "id": row.get("id") or "",
                    "published_date": row.get("published_date") or "",
                    "domain": row.get("domain") or "",
                    "source": row.get("source") or "",
                    "title_snippet": row.get("title_snippet") or "",
                    "query_used": row.get("query_used") or "",
                    "status": row.get("status") or "",
                    "url": row.get("url") or "",
                }
            )


def write_jsonl(path: Path, rows: Iterable[dict[str, object]], include_id: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if include_id:
                payload = dict(row)
            else:
                payload = {field: row.get(field) for field in DISCOVERED_FIELDS}
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def delete_rows(db_path: Path, removed_ids: list[int]) -> None:
    if not removed_ids:
        return
    placeholders = ",".join("?" for _ in removed_ids)
    with sqlite3.connect(db_path) as con:
        con.execute(f"delete from discovered_urls where id in ({placeholders})", removed_ids)
        con.commit()


def update_augmentation_state(path: Path, remaining_count: int) -> None:
    if not path.exists():
        return
    state = json.loads(path.read_text(encoding="utf-8"))

    def keep_query(query: object) -> bool:
        return not BLOCKED_RE.search(str(query or ""))

    state["keyword_rounds"] = [
        [query for query in round_queries if keep_query(query)]
        for round_queries in state.get("keyword_rounds", [])
    ]
    state["all_keywords"] = [
        query for query in state.get("all_keywords", []) if keep_query(query)
    ]
    state["article_counts"] = [remaining_count]
    state["ghee_cleanup"] = {
        "cleaned_at": datetime.now(timezone.utc).isoformat(),
        "rule": "removed discovered URLs and seed queries containing whole-word ghee or vanaspati",
        "remaining_discovered_urls": remaining_count,
    }
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()

    run_dir = args.run_dir
    output_dir = run_dir / "mediacloud" / "outputs"
    db_path = output_dir / "articles.db"
    discovered_jsonl = output_dir / "discovered_urls.jsonl"
    removed_csv = output_dir / "removed_ghee_urls.csv"
    removed_jsonl = output_dir / "removed_ghee_urls.jsonl"
    state_path = output_dir / "augmentation_state.json"

    if not db_path.exists():
        raise FileNotFoundError(f"Missing discovery database: {db_path}")

    rows = fetch_rows(db_path)
    removed_rows = [row for row in rows if is_blocked(row)]
    remaining_rows = [row for row in rows if not is_blocked(row)]

    write_removed_csv(removed_csv, removed_rows)
    write_jsonl(removed_jsonl, removed_rows, include_id=True)
    delete_rows(db_path, [int(row["id"]) for row in removed_rows])

    cleaned_rows = fetch_rows(db_path)
    write_jsonl(discovered_jsonl, cleaned_rows, include_id=False)
    update_augmentation_state(state_path, len(cleaned_rows))

    print(
        json.dumps(
            {
                "before": len(rows),
                "removed": len(removed_rows),
                "after": len(cleaned_rows),
                "removed_csv": str(removed_csv),
                "removed_jsonl": str(removed_jsonl),
                "rewritten_discovered_jsonl": str(discovered_jsonl),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
