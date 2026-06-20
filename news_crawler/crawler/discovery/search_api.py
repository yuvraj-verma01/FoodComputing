"""Search API discovery backends.

Supports three optional backends — only active when API key(s) are set:
  1. Google Custom Search Engine (CSE)
  2. Bing Web Search API v7
  3. SerpAPI (google organic results)

All three are behind runtime feature-flag checks so the crawler works
without any keys.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import urlparse

import requests

from ..config import Config

logger = logging.getLogger(__name__)


class SearchAPIDiscovery:
    """Wraps multiple search API backends behind a unified interface."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.delay = cfg.crawl_delay
        self._session = requests.Session()
        self._session.headers["User-Agent"] = cfg.user_agent

    def discover(self, queries: list[str]) -> Iterator[dict]:
        """Yield discovered-URL records from all enabled search API backends."""
        api_cfg = self.cfg.get("discovery", "search_api") or {}
        keys = self.cfg.get("api_keys") or {}

        for query in queries:
            # Google CSE
            if api_cfg.get("google_cse", {}).get("enabled"):
                k = keys.get("google_cse_key", "")
                cx = keys.get("google_cse_cx", "")
                if k and cx:
                    yield from self._google_cse(query, k, cx, api_cfg["google_cse"])
                    time.sleep(self.delay)

            # Bing
            if api_cfg.get("bing", {}).get("enabled"):
                k = keys.get("bing_api_key", "")
                if k:
                    yield from self._bing(query, k, api_cfg["bing"])
                    time.sleep(self.delay)

            # SerpAPI
            if api_cfg.get("serpapi", {}).get("enabled"):
                k = keys.get("serpapi_key", "")
                if k:
                    yield from self._serpapi(query, k, api_cfg["serpapi"])
                    time.sleep(self.delay)

    # ------------------------------------------------------------------

    def _google_cse(
        self, query: str, api_key: str, cx: str, sub_cfg: dict
    ) -> Iterator[dict]:
        num = int(sub_cfg.get("num_results", 10))
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": min(num, 10),
            "lr": "lang_en",
            "gl": "in",
            "dateRestrict": f"y{5}",
        }
        try:
            resp = self._session.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Google CSE error for '%s': %s", query, exc)
            return

        for item in data.get("items", []):
            url = item.get("link", "").strip()
            if not url:
                continue
            yield _make_record(
                url=url,
                method="google_cse",
                query=query,
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                pub_date=item.get("pagemap", {})
                .get("metatags", [{}])[0]
                .get("article:published_time", ""),
            )

    def _bing(self, query: str, api_key: str, sub_cfg: dict) -> Iterator[dict]:
        num = int(sub_cfg.get("num_results", 10))
        headers = {"Ocp-Apim-Subscription-Key": api_key}
        params = {
            "q": query,
            "count": min(num, 50),
            "mkt": "en-IN",
            "freshness": "Year",
        }
        try:
            resp = self._session.get(
                "https://api.bing.microsoft.com/v7.0/search",
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Bing API error for '%s': %s", query, exc)
            return

        for item in data.get("webPages", {}).get("value", []):
            url = item.get("url", "").strip()
            if not url:
                continue
            yield _make_record(
                url=url,
                method="bing",
                query=query,
                title=item.get("name", ""),
                snippet=item.get("snippet", ""),
                pub_date=item.get("datePublished", ""),
            )

    def _serpapi(self, query: str, api_key: str, sub_cfg: dict) -> Iterator[dict]:
        num = int(sub_cfg.get("num_results", 10))
        params = {
            "api_key": api_key,
            "engine": "google",
            "q": query,
            "num": min(num, 100),
            "gl": "in",
            "hl": "en",
            "tbs": "qdr:y5",
        }
        try:
            resp = self._session.get(
                "https://serpapi.com/search", params=params, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("SerpAPI error for '%s': %s", query, exc)
            return

        for item in data.get("organic_results", []):
            url = item.get("link", "").strip()
            if not url:
                continue
            yield _make_record(
                url=url,
                method="serpapi",
                query=query,
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                pub_date=item.get("date", ""),
            )

    def close(self) -> None:
        self._session.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_record(
    url: str,
    method: str,
    query: str,
    title: str = "",
    snippet: str = "",
    pub_date: str = "",
) -> dict:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    return {
        "url": url,
        "discovery_method": method,
        "query_used": query,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "title_snippet": f"{title} {snippet}".strip()[:500],
        "source": method,
        "domain": domain,
        "published_date": pub_date[:10] if pub_date else None,
        "status": "pending",
    }
