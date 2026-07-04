"""DuckDuckGo News discovery backend.

Searches DuckDuckGo News for recent articles and returns real article URLs —
no Google News redirect wrappers, no API key needed.

Uses the `ddgs` package (pip install ddgs).  Each query returns up to
max_results articles (default 30). Rate-limit: DDG throttles at ~60 req/min
per IP; we sleep `delay` seconds between queries.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import urlparse

from ..config import Config

logger = logging.getLogger(__name__)


class DDGSDiscovery:
    """Discovers article URLs via DuckDuckGo News search."""

    DISCOVERY_METHOD = "ddgs_news"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.delay = max(cfg.crawl_delay, 3.0)
        self.max_results = cfg.get("discovery", "ddgs_max_results") or 30

    def discover(self, queries: list[str]) -> Iterator[dict]:
        """Yield discovered-URL records for all queries."""
        try:
            from ddgs import DDGS  # type: ignore
        except ImportError:
            logger.warning(
                "ddgs not installed; DuckDuckGo News discovery skipped. "
                "Run: pip install ddgs"
            )
            return

        ddg = DDGS()
        for query in queries:
            try:
                yield from self._search(ddg, query)
            except Exception as exc:
                logger.warning("DDG News error for '%s': %s", query, exc)
            time.sleep(self.delay)

    def _search(self, ddg, query: str) -> Iterator[dict]:
        try:
            results = list(ddg.news(query, max_results=self.max_results))
        except Exception as exc:
            logger.warning("DDG News search failed for '%s': %s", query, exc)
            return

        logger.info("DDG News: query='%s' -> %d results", query, len(results))

        for item in results:
            url = item.get("url", "").strip()
            if not url or "news.google.com" in url:
                continue
            domain = urlparse(url).netloc.lower().removeprefix("www.")
            yield {
                "url": url,
                "discovery_method": self.DISCOVERY_METHOD,
                "query_used": query,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "title_snippet": item.get("title", "")[:500],
                "source": item.get("source", domain),
                "domain": domain,
                "published_date": _parse_date(item.get("date", "")),
                "status": "pending",
            }

    def close(self) -> None:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(date_str: str) -> str | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:19], fmt[:len(date_str[:19])]).date().isoformat()
        except ValueError:
            continue
    return None
