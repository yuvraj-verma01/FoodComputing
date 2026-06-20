"""Tests for the article extractor module."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.config import Config
from crawler.extractor import Extractor, _extract_html_meta, _clean_date


@pytest.fixture
def cfg():
    return Config()


@pytest.fixture
def extractor(cfg):
    return Extractor(cfg)


# Minimal synthetic HTML that looks like a news article
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>6000 litres of fake mustard oil seized in UP Barabanki</title>
  <meta property="og:title" content="6000 litres of fake mustard oil seized in UP" />
  <meta property="og:url" content="https://www.news18.com/india/fake-mustard-oil-barabanki" />
  <meta property="article:published_time" content="2024-03-10T08:30:00+05:30" />
  <link rel="canonical" href="https://www.news18.com/india/fake-mustard-oil-barabanki" />
  <script type="application/ld+json">
  {
    "@type": "NewsArticle",
    "headline": "6000 litres of fake mustard oil seized",
    "datePublished": "2024-03-10",
    "author": {"@type": "Person", "name": "Staff Reporter"}
  }
  </script>
</head>
<body>
  <nav>Navigation bar - should be removed</nav>
  <article>
    <h1>6000 litres of fake mustard oil seized in UP Barabanki</h1>
    <p>Police and food safety officials in Barabanki, Uttar Pradesh, seized approximately
    6,000 litres of fake mustard oil from an illegal godown on Tuesday. The oil was found
    to be adulterated with cheap palm oil and mineral oil.</p>
    <p>The FSSAI district officer confirmed that samples have been sent to an accredited
    laboratory for testing. The factory owner, identified as Ram Prasad, was arrested
    under the Food Safety and Standards Act, 2006.</p>
    <p>District Magistrate Anil Kumar said this was the third major seizure of adulterated
    edible oil in the district this month, raising concerns about food safety in the region.</p>
  </article>
  <footer>Copyright 2024 Example News</footer>
</body>
</html>
"""

MINIMAL_HTML = "<html><body><p>Short text</p></body></html>"


class TestHTMLMetaExtraction:
    def test_og_title_extracted(self):
        meta = _extract_html_meta(SAMPLE_HTML, "https://example.com")
        assert meta.get("title") is not None
        assert "mustard oil" in meta["title"].lower()

    def test_canonical_url_extracted(self):
        meta = _extract_html_meta(SAMPLE_HTML, "https://example.com")
        assert meta.get("canonical_url") == "https://www.news18.com/india/fake-mustard-oil-barabanki"

    def test_publication_date_extracted(self):
        meta = _extract_html_meta(SAMPLE_HTML, "https://example.com")
        assert meta.get("publication_date") == "2024-03-10"

    def test_author_from_json_ld(self):
        meta = _extract_html_meta(SAMPLE_HTML, "https://example.com")
        assert meta.get("author") == "Staff Reporter"


class TestDateCleaning:
    def test_iso_date_extracted(self):
        assert _clean_date("2024-03-10T08:30:00+05:30") == "2024-03-10"

    def test_plain_date_returned(self):
        assert _clean_date("2024-03-10") == "2024-03-10"

    def test_none_returns_none(self):
        assert _clean_date(None) is None

    def test_empty_returns_none(self):
        assert _clean_date("") is None


class TestFullExtraction:
    """Integration tests using BeautifulSoup fallback (no trafilatura needed)."""

    def test_extract_returns_dict(self, extractor):
        result = extractor.extract("https://example.com/test", SAMPLE_HTML)
        assert isinstance(result, dict)
        assert "url" in result
        assert "article_text" in result

    def test_extract_finds_article_text(self, extractor):
        result = extractor.extract("https://example.com/test", SAMPLE_HTML)
        if result["extraction_status"] in ("success", "partial"):
            text = result.get("article_text") or ""
            assert len(text) > 50, "Extracted text is too short"
            assert "mustard oil" in text.lower() or "barabanki" in text.lower()

    def test_extract_removes_nav_footer(self, extractor):
        result = extractor.extract("https://example.com/test", SAMPLE_HTML)
        if result.get("article_text"):
            assert "Navigation bar" not in result["article_text"]
            assert "Copyright 2024" not in result["article_text"]

    def test_minimal_html_handled_gracefully(self, extractor):
        result = extractor.extract("https://example.com/min", MINIMAL_HTML)
        assert result["extraction_status"] in ("success", "partial", "failed")
        assert "error_message" in result

    def test_metadata_overlay(self, extractor):
        result = extractor.extract("https://example.com/test", SAMPLE_HTML)
        # canonical URL should be filled from og:url or canonical link
        if result.get("canonical_url"):
            assert "news18" in result["canonical_url"] or "example" in result["canonical_url"]
