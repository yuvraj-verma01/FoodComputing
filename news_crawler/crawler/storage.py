"""Unified storage layer: SQLite + JSONL + CSV.

All writes are idempotent on (url). Duplicate URLs are silently skipped
by INSERT OR IGNORE in SQLite.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .config import Config

logger = logging.getLogger(__name__)

# ── Schema ────────────────────────────────────────────────────────────────────

DISCOVERED_DDL = """
CREATE TABLE IF NOT EXISTS discovered_urls (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    url              TEXT    NOT NULL UNIQUE,
    discovery_method TEXT,
    query_used       TEXT,
    discovered_at    TEXT,
    title_snippet    TEXT,
    source           TEXT,
    domain           TEXT,
    published_date   TEXT,
    status           TEXT    DEFAULT 'pending'  -- pending | downloaded | failed | skipped
);
"""

ARTICLES_DDL = """
CREATE TABLE IF NOT EXISTS articles (
    article_id           TEXT PRIMARY KEY,
    title                TEXT,
    url                  TEXT NOT NULL UNIQUE,
    canonical_url        TEXT,
    source               TEXT,
    domain               TEXT,
    author               TEXT,
    publication_date     TEXT,
    discovered_at        TEXT,
    crawled_at           TEXT,
    query_used           TEXT,
    discovery_method     TEXT,
    raw_html_path        TEXT,
    cleaned_text_path    TEXT,
    article_text         TEXT,
    modified_date        TEXT,
    food_terms_found     TEXT,   -- JSON list
    adulteration_terms_found TEXT,
    location_terms_found TEXT,
    action_terms_found   TEXT,
    incident_terms_found TEXT,
    relevance_score      REAL,
    relevance_label      TEXT,   -- relevant | maybe_relevant | irrelevant
    duplicate_cluster_id TEXT,
    is_duplicate         INTEGER DEFAULT 0,
    duplicate_of_url     TEXT,
    extraction_status    TEXT,   -- success | failed | partial
    extraction_method    TEXT,
    error_message        TEXT,
    text_hash            TEXT,
    word_count           INTEGER,
    notes                TEXT,
    -- NLP extraction placeholders (populated by later pipeline stage)
    nlp_food_item        TEXT,
    nlp_oil_type         TEXT,
    nlp_adulterant       TEXT,
    nlp_adulteration_type TEXT,
    nlp_quantity         TEXT,
    nlp_location_city    TEXT,
    nlp_location_district TEXT,
    nlp_location_state   TEXT,
    nlp_evidence_source  TEXT,
    nlp_incident_type    TEXT,
    nlp_impact_health    TEXT,
    nlp_impact_economic  TEXT,
    nlp_action_taken     TEXT,
    nlp_confidence_level REAL,
    nlp_fssai_category   TEXT,
    nlp_ontology_mapping TEXT,
    nlp_extraction_notes TEXT
);
"""

INDICES_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_articles_domain ON articles(domain);",
    "CREATE INDEX IF NOT EXISTS idx_articles_relevance ON articles(relevance_label);",
    "CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(publication_date);",
    "CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(duplicate_cluster_id);",
    "CREATE INDEX IF NOT EXISTS idx_disc_status ON discovered_urls(status);",
]


# ── Storage class ─────────────────────────────────────────────────────────────

class Storage:
    """Handles all persistence: SQLite, JSONL exports, CSV exports."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        db_path = cfg.path("db")
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

        self._jsonl_discovered = cfg.path("discovered_urls")
        self._jsonl_articles = cfg.path("articles_jsonl")
        self._csv_articles = cfg.path("articles_csv")

        self._csv_writer: Optional[csv.DictWriter] = None
        self._csv_file = None

        logger.info("Storage initialised at %s", db_path)

    # ── Schema ─────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(DISCOVERED_DDL + ARTICLES_DDL)
        for idx in INDICES_DDL:
            cur.execute(idx)
        self.conn.commit()

    # ── Discovered URLs ────────────────────────────────────────────────────

    def save_discovered(self, record: dict) -> bool:
        """Insert a discovered URL. Returns True if new, False if already exists."""
        sql = """
        INSERT OR IGNORE INTO discovered_urls
            (url, discovery_method, query_used, discovered_at,
             title_snippet, source, domain, published_date, status)
        VALUES
            (:url, :discovery_method, :query_used, :discovered_at,
             :title_snippet, :source, :domain, :published_date, :status)
        """
        defaults = {
            "discovery_method": None,
            "query_used": None,
            "discovered_at": _now(),
            "title_snippet": None,
            "source": None,
            "domain": None,
            "published_date": None,
            "status": "pending",
        }
        row = {**defaults, **record}
        cur = self.conn.execute(sql, row)
        self.conn.commit()
        is_new = cur.rowcount > 0
        if is_new:
            # Append to JSONL
            _append_jsonl(self._jsonl_discovered, row)
        return is_new

    def mark_discovered_status(self, url: str, status: str) -> None:
        self.conn.execute(
            "UPDATE discovered_urls SET status=? WHERE url=?", (status, url)
        )
        self.conn.commit()

    def get_pending_urls(self, limit: int = 0) -> list[dict]:
        sql = "SELECT * FROM discovered_urls WHERE status='pending'"
        if limit:
            sql += f" LIMIT {limit}"
        rows = self.conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

    def count_discovered(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM discovered_urls GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    # ── Articles ───────────────────────────────────────────────────────────

    def save_article(self, article: dict) -> bool:
        """Upsert an article. Returns True if new."""
        article = _prepare_article(article)
        fields = list(article.keys())
        placeholders = ", ".join(f":{f}" for f in fields)
        cols = ", ".join(fields)
        sql = f"INSERT OR IGNORE INTO articles ({cols}) VALUES ({placeholders})"
        cur = self.conn.execute(sql, article)
        self.conn.commit()
        is_new = cur.rowcount > 0
        if is_new:
            _append_jsonl(self._jsonl_articles, article)
        return is_new

    def update_article(self, url: str, updates: dict) -> None:
        """Patch specific columns on an existing article row."""
        if not updates:
            return
        set_clause = ", ".join(f"{k}=:{k}" for k in updates)
        updates["_url"] = url
        self.conn.execute(
            f"UPDATE articles SET {set_clause} WHERE url=:_url", updates
        )
        self.conn.commit()

    def article_exists(self, url: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM articles WHERE url=? LIMIT 1", (url,)
        ).fetchone()
        return row is not None

    def get_article(self, url: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM articles WHERE url=? LIMIT 1", (url,)
        ).fetchone()
        return dict(row) if row else None

    def iter_articles(
        self,
        label: Optional[str] = None,
        limit: int = 0,
    ) -> Iterator[dict]:
        sql = "SELECT * FROM articles"
        params: list[Any] = []
        if label:
            sql += " WHERE relevance_label=?"
            params.append(label)
        if limit:
            sql += f" LIMIT {limit}"
        for row in self.conn.execute(sql, params):
            yield dict(row)

    def count_articles(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT relevance_label, COUNT(*) AS n FROM articles GROUP BY relevance_label"
        ).fetchall()
        return {(r["relevance_label"] or "unknown"): r["n"] for r in rows}

    def count_duplicates(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM articles WHERE is_duplicate=1"
        ).fetchone()
        return row["n"] if row else 0

    # ── Exports ────────────────────────────────────────────────────────────

    def export_csv(self, path: Optional[Path] = None) -> Path:
        out = Path(path) if path else self._csv_articles
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = list(self.iter_articles())
        if not rows:
            logger.warning("No articles to export to CSV.")
            return out
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        logger.info("Exported %d articles to CSV: %s", len(rows), out)
        return out

    def export_jsonl(self, path: Optional[Path] = None) -> Path:
        """Re-export full articles JSONL from DB (canonical source of truth)."""
        out = Path(path) if path else self._jsonl_articles
        out.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with out.open("w", encoding="utf-8") as fh:
            for row in self.iter_articles():
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                n += 1
        logger.info("Exported %d articles to JSONL: %s", n, out)
        return out

    def close(self) -> None:
        self.conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _prepare_article(a: dict) -> dict:
    """Ensure required fields and serialise list fields to JSON strings."""
    a.setdefault("article_id", str(uuid.uuid4()))
    a.setdefault("crawled_at", _now())
    for list_field in (
        "food_terms_found",
        "adulteration_terms_found",
        "location_terms_found",
        "action_terms_found",
        "incident_terms_found",
    ):
        val = a.get(list_field)
        if isinstance(val, list):
            a[list_field] = json.dumps(val, ensure_ascii=False)

    # Compute text hash if text is present and hash not set
    text = a.get("article_text", "")
    if text and not a.get("text_hash"):
        a["text_hash"] = hashlib.sha256(text.encode()).hexdigest()
    if text and not a.get("word_count"):
        a["word_count"] = len(text.split())

    return a
