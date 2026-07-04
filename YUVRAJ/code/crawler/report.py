"""Run-summary report generator.

After each pipeline stage this module compiles statistics from the DB
and writes a JSON report plus a human-readable text summary.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import Config
from .storage import Storage

logger = logging.getLogger(__name__)


class Reporter:
    """Builds and saves pipeline run reports."""

    def __init__(self, cfg: Config, storage: Storage) -> None:
        self.cfg = cfg
        self.storage = storage
        self.report_path = cfg.path("report")

    # ------------------------------------------------------------------

    def build(self) -> dict:
        """Collect statistics and return report dict."""
        report: dict = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "date_range": {
                "start": self.cfg.date_start,
                "end": self.cfg.date_end,
            },
        }

        # Discovery stats
        disc_counts = self.storage.count_discovered()
        report["discovery"] = {
            "total_urls_found": sum(disc_counts.values()),
            "by_status": disc_counts,
        }

        # Article stats
        art_counts = self.storage.count_articles()
        total_articles = sum(art_counts.values())
        report["articles"] = {
            "total": total_articles,
            "by_relevance_label": art_counts,
            "duplicates_removed": self.storage.count_duplicates(),
        }

        # Top sources
        report["top_sources"] = self._top_field("domain", 15)

        # Top oil terms
        report["top_oil_terms"] = self._top_list_field("food_terms_found", 15)

        # Top adulteration terms
        report["top_adulteration_terms"] = self._top_list_field(
            "adulteration_terms_found", 15
        )

        # Top action terms
        report["top_action_terms"] = self._top_list_field("action_terms_found", 10)

        # Top locations
        report["top_locations"] = self._top_list_field("location_terms_found", 20)

        # Extraction method breakdown
        report["extraction_methods"] = self._top_field("extraction_method", 10)

        # Errors
        report["errors"] = self._count_errors()

        # Discovery methods
        report["discovery_methods"] = self._top_field_disc("discovery_method", 10)

        return report

    # ------------------------------------------------------------------

    def save(self, report: Optional[dict] = None) -> Path:
        """Build (if needed) and save report to JSON."""
        if report is None:
            report = self.build()
        with self.report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        logger.info("Report saved to %s", self.report_path)
        return self.report_path

    def print_summary(self, report: Optional[dict] = None) -> None:
        """Print a human-readable summary to stdout."""
        if report is None:
            report = self.build()

        lines = [
            "",
            "=" * 60,
            "  FOOD OIL ADULTERATION NEWS CRAWLER — RUN REPORT",
            "=" * 60,
            f"  Generated : {report['generated_at']}",
            f"  Date range: {report['date_range']['start']} to {report['date_range']['end']}",
            "",
            "── DISCOVERY ─────────────────────────────────────────────",
        ]

        disc = report.get("discovery", {})
        lines.append(f"  Total URLs found  : {disc.get('total_urls_found', 0)}")
        for status, n in sorted((disc.get("by_status") or {}).items()):
            lines.append(f"    {status:<18}: {n}")

        lines.append("")
        lines.append("── ARTICLES ──────────────────────────────────────────────")
        art = report.get("articles", {})
        lines.append(f"  Total articles    : {art.get('total', 0)}")
        for label, n in sorted((art.get("by_relevance_label") or {}).items()):
            lines.append(f"    {label:<18}: {n}")
        lines.append(f"  Duplicates removed: {art.get('duplicates_removed', 0)}")

        lines.append("")
        lines.append("── TOP SOURCES (by article count) ────────────────────────")
        for domain, n in (report.get("top_sources") or {}).items():
            lines.append(f"  {domain:<40} {n}")

        lines.append("")
        lines.append("── TOP OIL TERMS ─────────────────────────────────────────")
        for term, n in (report.get("top_oil_terms") or {}).items():
            lines.append(f"  {term:<30} {n}")

        lines.append("")
        lines.append("── TOP ADULTERATION TERMS ────────────────────────────────")
        for term, n in (report.get("top_adulteration_terms") or {}).items():
            lines.append(f"  {term:<30} {n}")

        lines.append("")
        lines.append("── TOP LOCATIONS FOUND ───────────────────────────────────")
        for loc, n in (report.get("top_locations") or {}).items():
            lines.append(f"  {loc:<30} {n}")

        lines.append("")
        lines.append("── EXTRACTION METHODS ────────────────────────────────────")
        for meth, n in (report.get("extraction_methods") or {}).items():
            lines.append(f"  {meth:<20} {n}")

        lines.append("")
        lines.append("── ERRORS ────────────────────────────────────────────────")
        errors = report.get("errors", {})
        lines.append(f"  Failed downloads  : {errors.get('failed_downloads', 0)}")
        lines.append(f"  robots_blocked    : {errors.get('robots_blocked', 0)}")
        lines.append(f"  Extraction failed : {errors.get('extraction_failed', 0)}")

        lines.append("=" * 60)
        lines.append("")

        import sys
        out = "\n".join(lines)
        sys.stdout.buffer.write((out + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()

    # ------------------------------------------------------------------
    # Stat helpers
    # ------------------------------------------------------------------

    def _top_field(self, field: str, n: int) -> dict[str, int]:
        """Count articles by a scalar DB column."""
        rows = self.storage.conn.execute(
            f"SELECT {field}, COUNT(*) AS cnt FROM articles "
            f"WHERE {field} IS NOT NULL GROUP BY {field} ORDER BY cnt DESC LIMIT ?",
            (n,),
        ).fetchall()
        return {r[field]: r["cnt"] for r in rows}

    def _top_field_disc(self, field: str, n: int) -> dict[str, int]:
        rows = self.storage.conn.execute(
            f"SELECT {field}, COUNT(*) AS cnt FROM discovered_urls "
            f"WHERE {field} IS NOT NULL GROUP BY {field} ORDER BY cnt DESC LIMIT ?",
            (n,),
        ).fetchall()
        return {r[field]: r["cnt"] for r in rows}

    def _top_list_field(self, field: str, n: int) -> dict[str, int]:
        """Explode a JSON list column and count term frequencies."""
        import json as _json

        rows = self.storage.conn.execute(
            f"SELECT {field} FROM articles WHERE {field} IS NOT NULL"
        ).fetchall()
        counter: Counter = Counter()
        for row in rows:
            try:
                terms = _json.loads(row[field] or "[]")
                counter.update(terms)
            except Exception:
                pass
        return dict(counter.most_common(n))

    def _count_errors(self) -> dict[str, int]:
        return {
            "failed_downloads": self.storage.conn.execute(
                "SELECT COUNT(*) FROM discovered_urls WHERE status='failed'"
            ).fetchone()[0],
            "robots_blocked": self.storage.conn.execute(
                "SELECT COUNT(*) FROM discovered_urls WHERE status='robots_blocked'"
            ).fetchone()[0],
            "extraction_failed": self.storage.conn.execute(
                "SELECT COUNT(*) FROM articles WHERE extraction_status='failed'"
            ).fetchone()[0],
        }
