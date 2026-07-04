"""Build focused search queries from configured term lists.

Strategy: combine (food_term) + (adulteration/action term) + (India/location).
High-priority queries are drawn from queries.yaml; auto-generated queries fill out
the rest up to max_queries.
"""

from __future__ import annotations

import logging
from itertools import product
from pathlib import Path
from typing import Iterator

import yaml

from .config import BASE_DIR, Config

logger = logging.getLogger(__name__)


def _load_manual_queries(queries_yaml: Path) -> list[str]:
    if not queries_yaml.exists():
        return []
    with queries_yaml.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    queries: list[str] = []
    for section in ("high_priority", "medium_priority", "supplementary"):
        queries.extend(data.get(section, []))
    return queries


def generate_queries(cfg: Config) -> list[str]:
    """Return deduplicated query strings, manual queries first.

    The final list respects cfg.get('query_builder','max_queries').
    Looks for queries_yaml path in cfg first, then falls back to
    config/queries.yaml next to config.yaml.
    """
    max_q = int(cfg.get("query_builder", "max_queries") or 300)
    # Allow overriding the queries file via config key
    custom_qf = cfg.get("query_builder", "queries_file")
    if custom_qf:
        queries_yaml = BASE_DIR / custom_qf
    else:
        queries_yaml = BASE_DIR / "config" / "queries.yaml"

    seen: set[str] = set()
    result: list[str] = []

    def _add(q: str) -> None:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            result.append(q)

    # 1. Manual queries from queries.yaml (highest priority)
    for q in _load_manual_queries(queries_yaml):
        _add(q)

    if len(result) >= max_q:
        return result[:max_q]

    # 2. Auto-generate: food_term × adulteration_term × "India"
    food_terms = cfg.food_terms
    adulteration_terms = cfg.adulteration_terms
    action_terms = cfg.action_terms
    india_anchors = ["India", "FSSAI"]

    # food × adulteration × India
    for ft, at, loc in product(food_terms, adulteration_terms, india_anchors):
        _add(f"{ft} {at} {loc}")
        if len(result) >= max_q:
            return result

    # food × action × India
    for ft, act, loc in product(food_terms, action_terms[:8], india_anchors):
        _add(f"{ft} {act} {loc}")
        if len(result) >= max_q:
            return result

    # food × adulteration (no explicit location; GDELT/search will geo-filter)
    for ft, at in product(food_terms[:10], adulteration_terms[:6]):
        _add(f"{ft} {at}")
        if len(result) >= max_q:
            return result

    logger.info("Generated %d queries", len(result))
    return result[:max_q]


def iter_queries(cfg: Config) -> Iterator[str]:
    """Yield each query one at a time (memory-friendly)."""
    yield from generate_queries(cfg)
