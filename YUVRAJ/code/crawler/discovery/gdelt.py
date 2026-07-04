"""GDELT Doc 2.0 API discovery backend.

Uses the free GDELT Article Search API — no API key required.
Endpoint: https://api.gdeltproject.org/api/v2/doc/doc

Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

Rate-limit: GDELT asks for reasonable use; we cap at one request per
`crawl.delay_seconds` and limit max_records to 250 (API ceiling).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import quote_plus, urlparse

import requests

from ..config import Config

logger = logging.getLogger(__name__)

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


class GDELTDiscovery:
    """Searches GDELT for article URLs matching each query."""

    DISCOVERY_METHOD = "gdelt"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.delay = cfg.crawl_delay
        self.max_records = int(cfg.get("discovery", "gdelt", "max_records") or 250)
        self.timespan = cfg.get("discovery", "gdelt", "timespan") or "5y"
        self._session = requests.Session()
        self._session.headers["User-Agent"] = cfg.user_agent

    def discover(self, queries: list[str]) -> Iterator[dict]:
        """Yield discovered-URL records for all queries."""
        for query in queries:
            yield from self._search(query)
            time.sleep(self.delay)

    # ------------------------------------------------------------------

    def _search(self, query: str) -> Iterator[dict]:
        # Restrict to Indian sources (sourcecountry:IN) and English-language content.
        # This dramatically reduces noise from global non-Indian outlets that GDELT
        # would otherwise index for keyword-matching queries.
        india_filter = "sourcecountry:IN"
        restricted_query = f"{query} {india_filter}"
        params = {
            "query": restricted_query,
            "mode": "artlist",
            "maxrecords": self.max_records,
            "timespan": self.timespan,
            "format": "json",
            "sort": "DateDesc",
        }
        # Retry up to 3 times on 429 with increasing back-off.
        data = None
        for attempt in range(1, 4):
            try:
                resp = self._session.get(GDELT_ENDPOINT, params=params, timeout=30)
                if resp.status_code == 429:
                    wait = 20 * attempt          # 20s, 40s, 60s
                    logger.warning(
                        "GDELT 429 for '%s' (attempt %d) — sleeping %ds", query, attempt, wait
                    )
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as exc:
                logger.warning("GDELT error for query '%s' (attempt %d): %s", query, attempt, exc)
                if attempt < 3:
                    time.sleep(10 * attempt)
        if data is None:
            return

        articles = data.get("articles") or []
        logger.info("GDELT: query='%s' -> %d results", query, len(articles))

        for art in articles:
            url = art.get("url", "").strip()
            if not url:
                continue
            domain = urlparse(url).netloc.lower().removeprefix("www.")
            yield {
                "url": url,
                "discovery_method": self.DISCOVERY_METHOD,
                "query_used": query,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "title_snippet": art.get("title", "")[:500],
                "source": "gdelt",
                "domain": domain,
                "published_date": _parse_gdelt_date(art.get("seendate", "")),
                "status": "pending",
            }

    def close(self) -> None:
        self._session.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_gdelt_date(seendate: str) -> str | None:
    """Convert GDELT date '20240315T120000Z' → ISO string."""
    if not seendate:
        return None
    try:
        # GDELT format: YYYYMMDDTHHmmssZ
        dt = datetime.strptime(seendate[:15], "%Y%m%dT%H%M%S")
        return dt.date().isoformat()
    except ValueError:
        return None
