"""Seed URL loader.

Reads URLs from:
  1. oil_sample_articles.docx  (auto-detected in project root)
  2. data/seeds/seed_urls.csv  (manually maintained list)
  3. Any additional CSV files passed explicitly

Each yielded record has the standard discovered-URL schema.
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from ..config import BASE_DIR, Config

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


class SeedLoader:
    """Loads seed URLs from local files."""

    DISCOVERY_METHOD = "seed"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    # ------------------------------------------------------------------

    def discover(self) -> Iterator[dict]:
        """Yield discovered-URL records from all seed sources."""
        yield from self._load_docx()
        yield from self._load_csv()

    # ------------------------------------------------------------------

    def _load_docx(self) -> Iterator[dict]:
        """Extract URLs from oil_sample_articles.docx."""
        docx_path = BASE_DIR.parent / "oil_sample_articles.docx"
        if not docx_path.exists():
            # also check one level up inside news_crawler
            docx_path = BASE_DIR / "oil_sample_articles.docx"
        if not docx_path.exists():
            logger.debug("oil_sample_articles.docx not found; skipping docx seed.")
            return

        try:
            import docx  # type: ignore
        except ImportError:
            logger.warning(
                "python-docx not installed; cannot load docx seeds. "
                "Run: pip install python-docx"
            )
            return

        try:
            doc = docx.Document(str(docx_path))
        except Exception as exc:
            logger.error("Failed to open %s: %s", docx_path, exc)
            return

        seen: set[str] = set()
        for para in doc.paragraphs:
            for url in _URL_RE.findall(para.text):
                url = url.rstrip(".,;)")
                if url not in seen:
                    seen.add(url)
                    yield _make_record(url, source=str(docx_path.name))

        logger.info("Loaded %d seed URLs from %s", len(seen), docx_path.name)

    def _load_csv(self) -> Iterator[dict]:
        """Load URLs from seed_urls.csv (url column required)."""
        csv_path = Path(self.cfg.get("paths", "seed_urls") or "")
        if not csv_path.exists():
            logger.debug("seed_urls.csv not found at %s; skipping.", csv_path)
            return

        seen: set[str] = set()
        with csv_path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                url = (row.get("url") or row.get("URL") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                rec = _make_record(url, source="seed_urls.csv")
                # Overlay optional CSV columns
                for col in ("title_snippet", "published_date", "query_used", "domain"):
                    val = row.get(col, "").strip()
                    if val:
                        rec[col] = val
                yield rec

        logger.info("Loaded %d seed URLs from seed_urls.csv", len(seen))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_record(url: str, source: str = "seed") -> dict:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    return {
        "url": url,
        "discovery_method": "seed",
        "query_used": None,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "title_snippet": None,
        "source": source,
        "domain": domain,
        "published_date": None,
        "status": "pending",
    }
