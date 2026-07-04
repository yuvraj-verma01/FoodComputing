"""Deduplication module.

Five layers (configurable):
  1. Exact URL match (DB primary key)
  2. Canonical URL normalisation
  3. Normalised title match
  4. SHA-256 text hash
  5. Near-duplicate detection via Jaccard similarity on word shingles

Duplicate clusters: if multiple articles share the same story (e.g. PTI/ANI
syndicated reports), one is elected primary and the rest store duplicate_of_url
+ duplicate_cluster_id.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
import uuid
from typing import Optional
from urllib.parse import parse_qs, urlparse, urlunparse

from .config import Config

logger = logging.getLogger(__name__)


class Deduplicator:
    """Detects and manages duplicate articles.

    Maintains in-memory indexes; persist them via the Storage layer.
    """

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        dc = cfg.get("dedupe") or {}
        self.do_url_exact = bool(dc.get("url_exact", True))
        self.do_url_canonical = bool(dc.get("url_canonical", True))
        self.do_title = bool(dc.get("title_normalize", True))
        self.do_text_hash = bool(dc.get("text_hash", True))
        self.do_near_dup = bool((dc.get("near_duplicate") or {}).get("enabled", True))
        self.similarity_threshold = float(
            (dc.get("near_duplicate") or {}).get("similarity_threshold", 0.85)
        )

        # In-memory indexes
        self._url_index: dict[str, str] = {}          # canonical_url → article_id
        self._title_index: dict[str, str] = {}         # norm_title → article_id
        self._hash_index: dict[str, str] = {}          # text_hash → article_id
        self._shingles_index: dict[str, set[int]] = {} # article_id → shingle set
        self._cluster_map: dict[str, str] = {}         # article_id → cluster_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_from_storage(self, storage) -> None:
        """Seed in-memory indexes from existing DB articles."""
        for art in storage.iter_articles():
            self._register(art)
        logger.info(
            "Deduplicator loaded: %d URLs, %d titles, %d hashes",
            len(self._url_index),
            len(self._title_index),
            len(self._hash_index),
        )

    def check(self, article: dict) -> tuple[bool, Optional[str]]:
        """Return (is_duplicate, duplicate_of_article_id) for an article.

        Does NOT modify state. Call `register()` after deciding to keep it.
        """
        url = article.get("url", "")
        canonical = normalize_url(url)
        title = article.get("title", "")
        text = article.get("article_text", "")
        text_hash = _hash_text(text)
        norm_title = _normalize_title(title)

        # Layer 1+2: exact / canonical URL
        if self.do_url_exact or self.do_url_canonical:
            existing_id = self._url_index.get(canonical)
            if existing_id:
                return True, existing_id

        # Layer 3: normalised title
        if self.do_title and norm_title and len(norm_title) > 10:
            existing_id = self._title_index.get(norm_title)
            if existing_id:
                return True, existing_id

        # Layer 4: text hash
        if self.do_text_hash and text_hash:
            existing_id = self._hash_index.get(text_hash)
            if existing_id:
                return True, existing_id

        # Layer 5: near-duplicate (Jaccard on 3-shingles)
        if self.do_near_dup and text:
            shingles = _shingles(text)
            for aid, existing_shingles in self._shingles_index.items():
                sim = _jaccard(shingles, existing_shingles)
                if sim >= self.similarity_threshold:
                    return True, aid

        return False, None

    def register(self, article: dict) -> str:
        """Add article to indexes. Returns cluster_id (new or existing)."""
        self._register(article)
        return self._cluster_map.get(article.get("article_id", ""), str(uuid.uuid4()))

    def _register(self, article: dict) -> None:
        aid = article.get("article_id", "")
        if not aid:
            return
        url = article.get("url", "")
        canonical = normalize_url(url)
        title = article.get("title", "")
        text = article.get("article_text", "")
        text_hash = _hash_text(text)
        norm_title = _normalize_title(title)

        self._url_index[canonical] = aid
        if url != canonical:
            self._url_index[url] = aid
        if norm_title and len(norm_title) > 10:
            self._title_index[norm_title] = aid
        if text_hash:
            self._hash_index[text_hash] = aid
        if text and self.do_near_dup:
            self._shingles_index[aid] = _shingles(text)

        # Assign cluster — if article has a cluster_id use it, else create new
        existing_cluster = article.get("duplicate_cluster_id")
        if existing_cluster:
            self._cluster_map[aid] = existing_cluster
        elif aid not in self._cluster_map:
            self._cluster_map[aid] = str(uuid.uuid4())

    def assign_cluster(self, article_id: str, duplicate_of_id: str) -> str:
        """Link article_id to the same cluster as duplicate_of_id."""
        cluster_id = self._cluster_map.get(duplicate_of_id, str(uuid.uuid4()))
        self._cluster_map[article_id] = cluster_id
        self._cluster_map.setdefault(duplicate_of_id, cluster_id)
        return cluster_id


# ── URL normalisation ─────────────────────────────────────────────────────────

# Query parameters that don't change content
_STRIP_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referrer", "fbclid", "gclid", "msclkid", "_ga", "source",
    "from", "via", "share", "s", "cmpid", "mod",
}


def normalize_url(url: str) -> str:
    """Return a canonical form of *url* for deduplication."""
    try:
        p = urlparse(url.strip())
        # Lowercase scheme + host
        scheme = p.scheme.lower()
        netloc = p.netloc.lower().removeprefix("www.")
        path = p.path.rstrip("/") or "/"
        # Filter tracking params
        qs = parse_qs(p.query, keep_blank_values=False)
        filtered = {k: v for k, v in qs.items() if k.lower() not in _STRIP_PARAMS}
        # Rebuild sorted query string
        sorted_qs = "&".join(
            f"{k}={v[0]}" for k, v in sorted(filtered.items())
        )
        return urlunparse((scheme, netloc, path, "", sorted_qs, ""))
    except Exception:
        return url


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_title(title: str) -> str:
    """Lower, strip punctuation, collapse whitespace.

    Joins digit groups separated by punctuation (e.g. '6,000' → '6000')
    so "6,000 litres seized" and "6000 litres seized" compare equal.
    """
    if not title:
        return ""
    t = unicodedata.normalize("NFKD", title.lower())
    # Join numbers split by commas/periods (e.g. "6,000" → "6000")
    t = re.sub(r"(\d)[,.](\d)", r"\1\2", t)
    # Replace remaining punctuation with spaces
    t = re.sub(r"[^\w\s]", " ", t)
    # Collapse spaces around digit sequences left by comma removal
    t = re.sub(r"(\d)\s+(\d)", r"\1\2", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _hash_text(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode()).hexdigest()


def _shingles(text: str, k: int = 3) -> set[int]:
    """Return set of hashed word k-shingles."""
    words = text.lower().split()
    return {hash(tuple(words[i : i + k])) for i in range(len(words) - k + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
