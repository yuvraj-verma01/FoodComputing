"""RSS feed discovery backend.

Fetches RSS/Atom feeds from Indian news sources listed in sources.yaml,
filters entries whose title/summary contain any food or adulteration term,
and yields discovered-URL records.

Uses feedparser (pip install feedparser).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import yaml

from ..config import BASE_DIR, Config

logger = logging.getLogger(__name__)


class RSSDiscovery:
    """Polls RSS/Atom feeds and filters relevant entries."""

    DISCOVERY_METHOD = "rss"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.delay = cfg.crawl_delay
        self._food_patterns = _compile_patterns(cfg.food_terms)
        self._adul_patterns = _compile_patterns(cfg.adulteration_terms + cfg.action_terms)
        feeds_cfg_path = BASE_DIR / "config" / "sources.yaml"
        self._feeds = _load_feeds(feeds_cfg_path)

    def discover(self) -> Iterator[dict]:
        """Yield relevant discovered-URL records from all configured feeds."""
        try:
            import feedparser  # type: ignore
        except ImportError:
            logger.warning(
                "feedparser not installed; RSS discovery skipped. "
                "Run: pip install feedparser"
            )
            return

        for feed_meta in self._feeds:
            feed_url = feed_meta.get("url", "")
            domain = feed_meta.get("domain", urlparse(feed_url).netloc.removeprefix("www."))
            feed_name = feed_meta.get("name", domain)
            logger.info("Fetching RSS: %s", feed_name)

            try:
                parsed = feedparser.parse(feed_url)
            except Exception as exc:
                logger.warning("RSS fetch failed for %s: %s", feed_url, exc)
                time.sleep(self.delay)
                continue

            n_yielded = 0
            for entry in parsed.get("entries", []):
                url = entry.get("link", "").strip()
                if not url:
                    continue
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                combined = f"{title} {summary}".lower()

                if not _any_match(self._food_patterns, combined):
                    continue
                if not _any_match(self._adul_patterns, combined):
                    continue

                pub_date = _parse_rss_date(entry)
                yield {
                    "url": url,
                    "discovery_method": self.DISCOVERY_METHOD,
                    "query_used": f"rss:{feed_name}",
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "title_snippet": title[:500],
                    "source": feed_name,
                    "domain": domain,
                    "published_date": pub_date,
                    "status": "pending",
                }
                n_yielded += 1

            logger.info("RSS %s -> %d relevant entries", feed_name, n_yielded)
            time.sleep(self.delay)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compile_patterns(terms: list[str]) -> list[re.Pattern]:
    return [re.compile(r"\b" + re.escape(t.lower()) + r"\b") for t in terms]


def _any_match(patterns: list[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def _load_feeds(sources_yaml: Path) -> list[dict]:
    if not sources_yaml.exists():
        logger.warning("sources.yaml not found at %s", sources_yaml)
        return []
    with sources_yaml.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("rss_feeds", [])


def _parse_rss_date(entry: dict) -> str | None:
    """Return ISO date string from an RSS entry's published_parsed field."""
    import time as time_module
    ts = entry.get("published_parsed") or entry.get("updated_parsed")
    if ts:
        try:
            dt = datetime(*ts[:6])
            return dt.date().isoformat()
        except Exception:
            pass
    return None
