"""Media Cloud discovery backend.

Media Cloud (https://search.mediacloud.org) is an open-source news archive
covering thousands of global news sources including major Indian newspapers.
It provides article metadata (URL, title, date, source) matching a keyword
query — the full article text must be fetched separately via the normal
crawl → extract pipeline.

Authentication
--------------
Set the environment variable MEDIACLOUD_API_KEY (or add it to .env).
Get a free key at https://search.mediacloud.org/user/profile

Python client
-------------
pip install mediacloud

Collections
-----------
Use `python -m crawler mc-collections` to browse India collections.
Default India collection IDs used when none are configured:
  34412118  -- India - National  (142 sources, featured)
  38379954  -- India - State & Local  (221 sources)
"""

from __future__ import annotations

import logging
import time
from datetime import date as _date_type
from datetime import datetime, timezone
from typing import Iterator, Optional
from urllib.parse import urlparse

from ..config import Config

logger = logging.getLogger(__name__)

# Default India collections (used when config has no collection_ids)
_INDIA_DEFAULT_COLLECTIONS = [34412118, 38379954]

# Correct REST API base for the sources/collections browser
_MC_SOURCES_BASE = "https://search.mediacloud.org/api/sources"


class MediaCloudDiscovery:
    """Discovers article URLs and metadata via the Media Cloud search API."""

    DISCOVERY_METHOD = "mediacloud"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.api_key = cfg.get("api_keys", "mediacloud_key") or ""
        if not self.api_key:
            raise ValueError(
                "MEDIACLOUD_API_KEY not set. "
                "Add it to .env or set the env variable."
            )
        raw_ids = cfg.get("discovery", "mediacloud", "collection_ids") or []
        self.collection_ids: list[int] = [int(i) for i in raw_ids] if raw_ids else _INDIA_DEFAULT_COLLECTIONS
        self.max_results: int = int(cfg.get("discovery", "mediacloud", "max_results") or 500)
        self.delay: float = max(float(cfg.get("discovery", "mediacloud", "delay_seconds") or 1.0), 1.0)
        self._mc_client = None

    # ── Public interface ───────────────────────────────────────────────────────

    def discover(self, queries: list[str]) -> Iterator[dict]:
        """Yield discovered-URL records for all queries."""
        client = self._get_client()
        for query in queries:
            try:
                yield from self._search(client, query)
            except Exception as exc:
                logger.warning("Media Cloud error for '%s': %s", query, exc)
            time.sleep(self.delay)

    def list_collections(self, name_filter: str = "india") -> list[dict]:
        """Return Media Cloud collections matching name_filter via REST API."""
        return self._rest_collection_list(name_filter)

    def close(self) -> None:
        pass

    # ── Internal search ───────────────────────────────────────────────────────

    def _search(self, client, query: str) -> Iterator[dict]:
        """Yield article records from Media Cloud for one query."""
        start_date = self.cfg.date_start
        end_date = self.cfg.date_end
        logger.info("Media Cloud: query='%s' dates=%s to %s", query, start_date, end_date)

        try:
            import mediacloud.api as _mc  # type: ignore
            if isinstance(client, _mc.SearchApi):
                yield from self._search_via_package(client, query, start_date, end_date)
                return
        except ImportError:
            pass

        logger.warning(
            "mediacloud package not installed. Run: pip install mediacloud"
        )

    def _search_via_package(
        self, client, query: str, start: str, end: str
    ) -> Iterator[dict]:
        """Use the official mediacloud Python package with story_list pagination."""
        # API requires datetime.date objects, not strings
        start_d = _date_type.fromisoformat(start)
        end_d = _date_type.fromisoformat(end)

        count = 0
        pagination_token: Optional[str] = None

        while count < self.max_results:
            page_size = min(100, self.max_results - count)
            try:
                stories, pagination_token = client.story_list(
                    query,
                    start_d,
                    end_d,
                    collection_ids=self.collection_ids,
                    pagination_token=pagination_token,
                    page_size=page_size,
                )
            except Exception as exc:
                logger.warning("Media Cloud story_list error for '%s': %s", query, exc)
                break

            if not stories:
                break

            for story in stories:
                if count >= self.max_results:
                    break
                rec = self._article_to_record(story, query)
                if rec:
                    yield rec
                    count += 1

            if not pagination_token:
                break

            time.sleep(self.delay)

        logger.info("Media Cloud: query='%s' -> %d results", query, count)

    def _rest_collection_list(self, name_filter: str) -> list[dict]:
        """List collections via REST API (Token auth required)."""
        import requests as _req
        headers = {"Authorization": f"Token {self.api_key}"}
        try:
            resp = _req.get(
                f"{_MC_SOURCES_BASE}/collections/",
                params={"name": name_filter, "page_size": 50},
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results") or []
        except Exception as exc:
            logger.warning("Media Cloud collection list error: %s", exc)
            return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_client(self):
        """Return mc.SearchApi instance."""
        if self._mc_client is not None:
            return self._mc_client
        try:
            import mediacloud.api as _mc  # type: ignore
            self._mc_client = _mc.SearchApi(self.api_key)
            logger.info("Using mediacloud Python package")
        except ImportError:
            logger.warning(
                "mediacloud package not found. Install with: pip install mediacloud"
            )
            self._mc_client = object()  # sentinel triggers warning in _search
        return self._mc_client

    def _article_to_record(self, article: dict, query: str) -> Optional[dict]:
        """Convert a Media Cloud story dict to a discovered_urls record."""
        url = (article.get("url") or article.get("article_url") or "").strip()
        if not url or not url.startswith("http"):
            return None
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        raw_date = article.get("publish_date") or article.get("published_at") or ""
        # story_list returns datetime.date objects; also handle strings
        if hasattr(raw_date, "isoformat"):
            pub_date = raw_date.isoformat()
        else:
            pub_date = _parse_mc_date(str(raw_date) if raw_date else "")
        return {
            "url": url,
            "discovery_method": self.DISCOVERY_METHOD,
            "query_used": query,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "title_snippet": (article.get("title") or "")[:500],
            "source": article.get("media_name") or article.get("source_name") or domain,
            "domain": domain,
            "published_date": pub_date,
            "status": "pending",
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_mc_date(date_str: str) -> Optional[str]:
    """Parse Media Cloud date format to ISO date string."""
    if not date_str:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(date_str[:19], fmt[:len(date_str[:19])]).date().isoformat()
        except ValueError:
            continue
    return None
