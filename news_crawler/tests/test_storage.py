"""Tests for the Storage module."""

import json
import pytest
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.config import Config
from crawler.storage import Storage


@pytest.fixture
def tmp_cfg(tmp_path, monkeypatch):
    """Config that uses a temporary directory for all paths."""
    cfg = Config()
    # Patch paths to use tmp_path
    paths = cfg.raw["paths"]
    paths["db"] = str(tmp_path / "test.db")
    paths["raw_html"] = str(tmp_path / "raw_html")
    paths["cleaned_text"] = str(tmp_path / "cleaned_text")
    paths["outputs"] = str(tmp_path / "outputs")
    paths["logs"] = str(tmp_path / "logs")
    paths["discovered_urls"] = str(tmp_path / "outputs" / "discovered_urls.jsonl")
    paths["articles_jsonl"] = str(tmp_path / "outputs" / "articles.jsonl")
    paths["articles_csv"] = str(tmp_path / "outputs" / "articles.csv")
    paths["report"] = str(tmp_path / "outputs" / "report.json")
    return cfg


@pytest.fixture
def storage(tmp_cfg):
    s = Storage(tmp_cfg)
    yield s
    s.close()


def _disc_rec(url="https://example.com/test-article"):
    return {
        "url": url,
        "discovery_method": "seed",
        "query_used": "mustard oil adulteration India",
        "discovered_at": "2024-01-01T00:00:00+00:00",
        "title_snippet": "Test article title",
        "source": "test",
        "domain": "example.com",
        "published_date": "2024-01-01",
        "status": "pending",
    }


def _article_rec(url="https://example.com/test-article"):
    return {
        "article_id": str(uuid.uuid4()),
        "url": url,
        "canonical_url": url,
        "title": "Test article about mustard oil adulteration",
        "domain": "example.com",
        "source": "test",
        "article_text": "Mustard oil was adulterated with palm oil in UP. FSSAI seized 5000 litres.",
        "publication_date": "2024-01-01",
        "relevance_score": 0.75,
        "relevance_label": "relevant",
        "food_terms_found": ["mustard oil", "palm oil"],
        "adulteration_terms_found": ["adulterated"],
        "extraction_status": "success",
    }


class TestDiscoveredURLs:
    def test_save_discovered_new(self, storage):
        rec = _disc_rec()
        assert storage.save_discovered(rec) is True

    def test_save_discovered_duplicate_returns_false(self, storage):
        rec = _disc_rec()
        storage.save_discovered(rec)
        assert storage.save_discovered(rec) is False

    def test_get_pending_urls(self, storage):
        storage.save_discovered(_disc_rec("https://example.com/a"))
        storage.save_discovered(_disc_rec("https://example.com/b"))
        pending = storage.get_pending_urls()
        assert len(pending) == 2

    def test_mark_status(self, storage):
        rec = _disc_rec()
        storage.save_discovered(rec)
        storage.mark_discovered_status(rec["url"], "downloaded")
        pending = storage.get_pending_urls()
        assert len(pending) == 0

    def test_count_discovered(self, storage):
        storage.save_discovered(_disc_rec("https://example.com/a"))
        storage.save_discovered(_disc_rec("https://example.com/b"))
        storage.mark_discovered_status("https://example.com/a", "success")
        counts = storage.count_discovered()
        assert counts.get("pending", 0) == 1
        assert counts.get("success", 0) == 1


class TestArticles:
    def test_save_article_new(self, storage):
        art = _article_rec()
        assert storage.save_article(art) is True

    def test_save_article_duplicate_url_ignored(self, storage):
        art = _article_rec()
        storage.save_article(art)
        art2 = _article_rec()  # same URL
        art2["article_id"] = str(uuid.uuid4())
        assert storage.save_article(art2) is False

    def test_article_exists(self, storage):
        art = _article_rec()
        storage.save_article(art)
        assert storage.article_exists(art["url"])
        assert not storage.article_exists("https://notexist.com/x")

    def test_get_article(self, storage):
        art = _article_rec()
        storage.save_article(art)
        fetched = storage.get_article(art["url"])
        assert fetched is not None
        assert fetched["title"] == art["title"]

    def test_update_article(self, storage):
        art = _article_rec()
        storage.save_article(art)
        storage.update_article(art["url"], {"relevance_label": "maybe_relevant"})
        fetched = storage.get_article(art["url"])
        assert fetched["relevance_label"] == "maybe_relevant"

    def test_count_articles_by_label(self, storage):
        storage.save_article(_article_rec("https://example.com/a"))
        art2 = _article_rec("https://example.com/b")
        art2["relevance_label"] = "maybe_relevant"
        storage.save_article(art2)
        counts = storage.count_articles()
        assert counts.get("relevant", 0) == 1
        assert counts.get("maybe_relevant", 0) == 1

    def test_list_terms_serialised_as_json(self, storage):
        art = _article_rec()
        storage.save_article(art)
        fetched = storage.get_article(art["url"])
        terms = fetched.get("food_terms_found")
        # Should be stored as JSON string
        assert isinstance(terms, str)
        parsed = json.loads(terms)
        assert "mustard oil" in parsed

    def test_text_hash_computed(self, storage):
        art = _article_rec()
        storage.save_article(art)
        fetched = storage.get_article(art["url"])
        assert fetched.get("text_hash") is not None
        assert len(fetched["text_hash"]) == 64  # SHA-256 hex

    def test_word_count_computed(self, storage):
        art = _article_rec()
        storage.save_article(art)
        fetched = storage.get_article(art["url"])
        assert fetched.get("word_count", 0) > 0


class TestExports:
    def test_export_csv(self, storage, tmp_path):
        storage.save_article(_article_rec("https://example.com/a"))
        path = storage.export_csv(tmp_path / "out.csv")
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "mustard oil" in content

    def test_export_jsonl(self, storage, tmp_path):
        storage.save_article(_article_rec("https://example.com/a"))
        path = storage.export_jsonl(tmp_path / "out.jsonl")
        assert path.exists()
        with path.open() as f:
            line = json.loads(f.readline())
        assert "url" in line
