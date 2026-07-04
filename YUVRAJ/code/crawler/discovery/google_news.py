"""Google News RSS discovery backend.

Queries Google News search via its public RSS endpoint — no API key needed.
Results are pre-filtered to India (gl=IN) and English (hl=en-IN).

URL pattern:
  https://news.google.com/rss/search?q=<query>&hl=en-IN&gl=IN&ceid=IN:en

Google News RSS links are redirect wrappers (news.google.com/rss/articles/CBMi...).
The actual article URL is base64+protobuf encoded in the path — we decode it here
so the stored URLs are real article URLs that can be crawled directly.

Each query returns up to ~100 recent articles. Unlike GDELT, Google News
does not aggressively rate-limit individual search queries.
"""

from __future__ import annotations

import base64
import logging
import re
import time
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import quote_plus, urlparse

from ..config import Config

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


class GoogleNewsDiscovery:
    """Discovers article URLs via Google News RSS search queries."""

    DISCOVERY_METHOD = "google_news_rss"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.delay = max(cfg.crawl_delay, 3.0)  # minimum 3s between requests

    def discover(self, queries: list[str]) -> Iterator[dict]:
        """Yield discovered-URL records for all queries."""
        try:
            import feedparser  # type: ignore
        except ImportError:
            logger.warning(
                "feedparser not installed; Google News RSS discovery skipped. "
                "Run: pip install feedparser"
            )
            return

        for query in queries:
            yield from self._search(query, feedparser)
            time.sleep(self.delay)

    def _search(self, query: str, feedparser) -> Iterator[dict]:
        rss_url = (
            f"{GOOGLE_NEWS_RSS}"
            f"?q={quote_plus(query)}"
            f"&hl=en-IN&gl=IN&ceid=IN%3Aen"
        )
        try:
            feed = feedparser.parse(rss_url)
        except Exception as exc:
            logger.warning("Google News RSS error for '%s': %s", query, exc)
            return

        entries = feed.get("entries", [])
        logger.info("Google News RSS: query='%s' -> %d results", query, len(entries))

        for entry in entries:
            raw_url = entry.get("link", "").strip()
            if not raw_url:
                continue
            # Decode the Google News redirect via base64. If decoding fails the
            # URL still points to news.google.com — skip it entirely because
            # neither requests nor Playwright can resolve it (Google returns 400
            # to all headless browser requests on that endpoint).
            article_url = _decode_google_news_url(raw_url)
            if "news.google.com" in article_url:
                logger.debug("Could not decode GNews URL, skipping: %s", raw_url[:80])
                continue
            domain = urlparse(article_url).netloc.lower().removeprefix("www.")
            pub_date = _parse_entry_date(entry)
            source_tag = entry.get("source")
            source_name = (source_tag.get("title") if isinstance(source_tag, dict) else None) or domain
            yield {
                "url": article_url,
                "discovery_method": self.DISCOVERY_METHOD,
                "query_used": query,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "title_snippet": entry.get("title", "")[:500],
                "source": source_name,
                "domain": domain,
                "published_date": pub_date,
                "status": "pending",
            }

    def close(self) -> None:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decode_google_news_url(redirect_url: str) -> str:
    """Decode a Google News RSS redirect URL (news.google.com/rss/articles/CBMi...).

    Google News encodes the real article URL in the path using base64url + a
    short protobuf header. The structure is:
        3-byte protobuf field header  (0x08 0x13 0x22)
        1-byte varint string length
        N bytes: the article URL as UTF-8

    We base64-decode the path segment and search for any `https?://` URL within
    the decoded bytes, returning the first match.
    """
    if "news.google.com" not in redirect_url:
        return redirect_url

    # Strip query parameters (?oc=5 etc.) before decoding
    path_match = re.search(r'/articles/([A-Za-z0-9_\-]+)', redirect_url)
    if not path_match:
        return redirect_url

    encoded = path_match.group(1)
    # Add base64 padding
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding

    try:
        decoded = base64.urlsafe_b64decode(encoded)
        # Find the first http(s):// URL in the decoded bytes
        url_match = re.search(rb'https?://[^\x00-\x1f\x7f-\xff\s]+', decoded)
        if url_match:
            candidate = url_match.group(0).decode("utf-8", errors="replace")
            # Trim trailing control chars or nulls that slipped through
            candidate = re.sub(r'[\x00-\x1f\x7f]+.*$', '', candidate)
            return candidate
    except Exception as exc:
        logger.debug("Could not decode Google News URL %s: %s", redirect_url, exc)

    return redirect_url


def _parse_entry_date(entry: dict) -> str | None:
    """Return ISO date string from RSS entry."""
    ts = entry.get("published_parsed") or entry.get("updated_parsed")
    if ts:
        try:
            dt = datetime(*ts[:6])
            return dt.date().isoformat()
        except Exception:
            pass
    return None
