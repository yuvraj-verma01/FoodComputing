"""Tests for the query builder module."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.config import Config
from crawler.query_builder import generate_queries, iter_queries


@pytest.fixture
def cfg():
    return Config()


class TestGenerateQueries:
    def test_returns_list(self, cfg):
        queries = generate_queries(cfg)
        assert isinstance(queries, list)
        assert len(queries) > 0

    def test_no_duplicates(self, cfg):
        queries = generate_queries(cfg)
        lower = [q.lower() for q in queries]
        assert len(lower) == len(set(lower)), "Duplicate queries found"

    def test_respects_max_queries(self, cfg):
        queries = generate_queries(cfg)
        max_q = cfg.get("query_builder", "max_queries") or 300
        assert len(queries) <= max_q

    def test_high_priority_queries_first(self, cfg):
        queries = generate_queries(cfg)
        # The first query should be one of the manually defined high-priority ones
        assert "edible oil adulteration India" in queries[:10]

    def test_queries_contain_oil_terms(self, cfg):
        queries = generate_queries(cfg)
        oil_terms = cfg.food_terms
        hits = sum(
            1 for q in queries
            if any(t.lower() in q.lower() for t in oil_terms)
        )
        assert hits > len(queries) * 0.5, "Less than 50% of queries contain oil terms"

    def test_queries_contain_india(self, cfg):
        queries = generate_queries(cfg)
        india_hits = sum(1 for q in queries if "india" in q.lower() or "fssai" in q.lower())
        assert india_hits > 0

    def test_iter_queries_yields_same(self, cfg):
        from_list = generate_queries(cfg)
        from_iter = list(iter_queries(cfg))
        assert from_list == from_iter


class TestQueryContent:
    EXPECTED_QUERIES = [
        "mustard oil adulteration India",
        "fake mustard oil seized India",
        "spurious edible oil raid India",
        "adulterated cooking oil FSSAI",
        "FSSAI edible oil samples failed",
    ]

    def test_expected_queries_present(self, cfg):
        queries = generate_queries(cfg)
        for expected in self.EXPECTED_QUERIES:
            assert expected in queries, f"Expected query not found: '{expected}'"
