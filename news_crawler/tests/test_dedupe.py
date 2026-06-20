"""Tests for the deduplication module."""

import pytest
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.config import Config
from crawler.dedupe import Deduplicator, normalize_url


@pytest.fixture
def cfg():
    return Config()


@pytest.fixture
def dedup(cfg):
    return Deduplicator(cfg)


def _article(url, title=None, text=None):
    # Use url-derived defaults so every call generates unique title and text
    slug = url.split("/")[-1] or url[-20:]
    title = title or f"Article about {slug}"
    text = text or f"Unique article content for {slug}. Edible oil adulteration case."
    return {
        "article_id": str(uuid.uuid4()),
        "url": url,
        "canonical_url": url,
        "title": title,
        "article_text": text,
    }


class TestURLNormalisation:
    def test_strips_utm_params(self):
        url = "https://example.com/article?utm_source=google&utm_medium=cpc"
        assert normalize_url(url) == "https://example.com/article"

    def test_strips_www(self):
        url1 = "https://www.timesofindia.com/article/123"
        url2 = "https://timesofindia.com/article/123"
        assert normalize_url(url1) == normalize_url(url2)

    def test_strips_trailing_slash(self):
        url1 = "https://example.com/article/"
        url2 = "https://example.com/article"
        assert normalize_url(url1) == normalize_url(url2)

    def test_lowercases_host(self):
        url = "https://TimeOfIndia.COM/path"
        assert normalize_url(url).startswith("https://timeofindia.com")

    def test_preserves_content_params(self):
        url = "https://example.com/article?id=12345"
        assert "id=12345" in normalize_url(url)

    def test_seed_urls_normalise_consistently(self):
        urls = [
            "https://www.timesofindia.indiatimes.com/city/jaipur/article?utm_source=fb",
            "https://timesofindia.indiatimes.com/city/jaipur/article",
        ]
        assert normalize_url(urls[0]) == normalize_url(urls[1])


class TestExactDuplicate:
    def test_same_url_is_duplicate(self, dedup):
        art1 = _article("https://example.com/article-1")
        art2 = _article("https://example.com/article-1", title="Different title")
        dedup.register(art1)
        is_dup, dup_of = dedup.check(art2)
        assert is_dup
        assert dup_of == art1["article_id"]

    def test_different_url_not_duplicate(self, dedup):
        art1 = _article("https://example.com/article-1")
        art2 = _article("https://example.com/article-2")
        dedup.register(art1)
        is_dup, _ = dedup.check(art2)
        assert not is_dup


class TestTitleDuplicate:
    def test_same_title_is_duplicate(self, dedup):
        title = "6000 litres of fake mustard oil seized in Barabanki"
        art1 = _article("https://news18.com/article-1", title=title)
        art2 = _article("https://ndtv.com/article-2", title=title)
        dedup.register(art1)
        is_dup, dup_of = dedup.check(art2)
        assert is_dup

    def test_title_with_different_punctuation(self, dedup):
        art1 = _article(
            "https://example.com/a",
            title="Fake mustard oil: 6,000 litres seized!"
        )
        art2 = _article(
            "https://other.com/b",
            title="Fake mustard oil 6000 litres seized"
        )
        dedup.register(art1)
        is_dup, _ = dedup.check(art2)
        assert is_dup


class TestTextHashDuplicate:
    def test_identical_text_is_duplicate(self, dedup):
        text = (
            "Food safety officials in Kanpur seized 14,000 litres of adulterated "
            "cooking oil mixed with mineral oil. FSSAI lab tests confirmed the adulteration. "
            "The factory owner was arrested and an FIR was registered under the Food Safety "
            "and Standards Act 2006."
        )
        art1 = _article("https://example.com/a", text=text)
        art2 = _article("https://example.com/b", text=text)
        dedup.register(art1)
        is_dup, _ = dedup.check(art2)
        assert is_dup


class TestNearDuplicate:
    def test_near_duplicate_detected(self, dedup):
        # Both texts are the same PTI wire story republished by two outlets with
        # only minor word changes — Jaccard similarity should be well above threshold.
        base_text = (
            "Food safety officials in Uttar Pradesh have seized over four lakh litres of "
            "substandard edible oil during a state-wide crackdown launched last week. "
            "The drive was conducted under the supervision of the FSSAI regional office "
            "in Lucknow. Officials inspected over 200 storage facilities and collection "
            "points across the state. Multiple FIRs have been registered against the "
            "factory owners and six persons were arrested. The seized oil was found to "
            "be adulterated with cheaper palm oil and mineral traces. Samples have been "
            "sent to accredited FSSAI laboratories for analysis. The district magistrate "
            "confirmed that legal proceedings are underway under the Food Safety and "
            "Standards Act 2006."
        )
        variant_text = (
            "Food safety officials in Uttar Pradesh have seized over four lakh litres of "
            "substandard edible oil during a state-wide crackdown launched last week. "
            "The drive was conducted under the supervision of the FSSAI regional office "
            "in Lucknow. Officials inspected over 200 storage facilities and collection "
            "points across the state. Multiple FIRs have been registered against the "
            "factory owners and six persons were arrested. The seized oil was found to "
            "be adulterated with cheaper palm oil and mineral traces. Samples have been "
            "sent to accredited FSSAI laboratories for testing. The district magistrate "
            "confirmed that legal action is underway under the Food Safety and "
            "Standards Act 2006."
        )
        art1 = _article("https://theprint.in/article", text=base_text)
        art2 = _article("https://ndtv.com/same-story", text=variant_text)
        dedup.register(art1)
        is_dup, _ = dedup.check(art2)
        assert is_dup, "Near-duplicate should be detected"

    def test_distinct_articles_not_duplicate(self, dedup):
        art1 = _article(
            "https://example.com/a",
            text="Mustard oil adulteration case in Rajasthan. FSSAI seized 500 kg.",
        )
        art2 = _article(
            "https://example.com/b",
            text="Coconut oil banned in Kerala due to substandard quality. 45 brands delisted.",
        )
        dedup.register(art1)
        is_dup, _ = dedup.check(art2)
        assert not is_dup


class TestClusterManagement:
    def test_duplicate_assigned_to_same_cluster(self, dedup):
        art1 = _article("https://example.com/primary", title="Mustard oil seized Rajasthan")
        art2 = _article("https://example.com/copy", title="Mustard oil seized Rajasthan")
        dedup.register(art1)
        is_dup, dup_of = dedup.check(art2)
        assert is_dup
        cluster = dedup.assign_cluster(art2["article_id"], art1["article_id"])
        primary_cluster = dedup._cluster_map.get(art1["article_id"])
        assert cluster == primary_cluster
