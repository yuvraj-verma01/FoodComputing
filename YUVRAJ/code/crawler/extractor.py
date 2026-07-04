"""Article text extraction with multi-library fallback chain.

Priority:
  1. trafilatura  — best at boilerplate removal
  2. newspaper4k / newspaper3k  — strong metadata extraction
  3. BeautifulSoup  — last-resort plain-text fallback

Also extracts structured metadata from:
  - OpenGraph tags
  - Twitter Card tags
  - JSON-LD schema.org/NewsArticle
  - Standard HTML meta tags
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .config import Config

logger = logging.getLogger(__name__)


class Extractor:
    """Extracts article text and metadata from raw HTML."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.cleaned_text_dir = cfg.path("cleaned_text")

    def extract(self, url: str, html: str, raw_html_path: Optional[str] = None) -> dict:
        """Extract article from *html* and return a metadata/content dict."""
        result: dict = {
            "url": url,
            "canonical_url": None,
            "domain": urlparse(url).netloc.removeprefix("www."),
            "title": None,
            "article_text": None,
            "author": None,
            "publication_date": None,
            "modified_date": None,
            "extraction_status": "failed",
            "extraction_method": None,
            "error_message": None,
            "raw_html_path": raw_html_path,
            "cleaned_text_path": None,
            "word_count": 0,
        }

        # 1. Try trafilatura
        text, meta = _try_trafilatura(url, html)
        if text and len(text.split()) > 30:
            result.update(meta)
            result["article_text"] = text
            result["extraction_method"] = "trafilatura"
            result["extraction_status"] = "success"
            logger.debug("trafilatura ok: %s (%d words)", url, len(text.split()))
        else:
            # 2. Try newspaper
            text, meta = _try_newspaper(url, html)
            if text and len(text.split()) > 30:
                result.update(meta)
                result["article_text"] = text
                result["extraction_method"] = "newspaper"
                result["extraction_status"] = "success"
                logger.debug("newspaper ok: %s (%d words)", url, len(text.split()))
            else:
                # 3. BeautifulSoup fallback
                text, meta = _try_bs4(url, html)
                if text and len(text.split()) > 20:
                    result.update(meta)
                    result["article_text"] = text
                    result["extraction_method"] = "beautifulsoup"
                    result["extraction_status"] = "partial"
                    logger.debug("bs4 fallback: %s (%d words)", url, len(text.split()))
                else:
                    result["extraction_status"] = "failed"
                    result["error_message"] = "All extractors returned insufficient text"
                    logger.warning("Extraction failed: %s", url)

        # Overlay HTML metadata (may fill in missing fields)
        html_meta = _extract_html_meta(html, url)
        for k, v in html_meta.items():
            if v and not result.get(k):
                result[k] = v

        # Save cleaned text
        if result.get("article_text"):
            text = result["article_text"]
            result["word_count"] = len(text.split())
            result["cleaned_text_path"] = str(self._save_cleaned(url, text))

        return result

    # ------------------------------------------------------------------

    def _save_cleaned(self, url: str, text: str) -> Path:
        domain = urlparse(url).netloc.removeprefix("www.")
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        domain_dir = self.cleaned_text_dir / re.sub(r"[^\w\-.]", "_", domain)
        domain_dir.mkdir(parents=True, exist_ok=True)
        path = domain_dir / f"{url_hash}.txt"
        path.write_text(text, encoding="utf-8")
        return path


# ── Extractor backends ────────────────────────────────────────────────────────

def _try_trafilatura(url: str, html: str) -> tuple[str, dict]:
    try:
        import trafilatura  # type: ignore
        from trafilatura.settings import use_config  # type: ignore

        tconfig = use_config()
        tconfig.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")

        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            output_format="txt",
            config=tconfig,
        )
        meta_result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            output_format="json",
            config=tconfig,
        )
        meta: dict = {}
        if meta_result:
            try:
                m = json.loads(meta_result)
                meta["title"] = m.get("title")
                meta["author"] = m.get("author")
                meta["publication_date"] = _clean_date(m.get("date"))
                meta["canonical_url"] = m.get("url") or url
            except Exception:
                pass
        return result or "", meta
    except ImportError:
        return "", {}
    except Exception as exc:
        logger.debug("trafilatura error for %s: %s", url, exc)
        return "", {}


def _try_newspaper(url: str, html: str) -> tuple[str, dict]:
    # Try newspaper4k first, fall back to newspaper3k
    for pkg in ("newspaper4k", "newspaper"):
        try:
            if pkg == "newspaper4k":
                import newspaper  # type: ignore  # newspaper4k uses same import
            else:
                import newspaper  # type: ignore

            from newspaper import Article  # type: ignore

            article = Article(url)
            article.set_html(html)
            article.parse()
            text = article.text or ""
            meta: dict = {
                "title": article.title,
                "author": ", ".join(article.authors) if article.authors else None,
                "publication_date": _clean_date(
                    article.publish_date.isoformat() if article.publish_date else None
                ),
                "canonical_url": url,
            }
            return text, meta
        except ImportError:
            continue
        except Exception as exc:
            logger.debug("newspaper error for %s: %s", url, exc)
            return "", {}
    return "", {}


def _try_bs4(url: str, html: str) -> tuple[str, dict]:
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")

        # Remove boilerplate tags
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "noscript", "iframe", "ads"]):
            tag.decompose()

        # Try to find article body
        body = (
            soup.find("article")
            or soup.find(class_=re.compile(r"article[_-]?(body|content|text)", re.I))
            or soup.find(id=re.compile(r"article[_-]?(body|content|text)", re.I))
            or soup.find("main")
            or soup.find("body")
        )
        text = body.get_text(separator="\n", strip=True) if body else ""
        # Collapse excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        return text, {"title": title, "canonical_url": url}
    except ImportError:
        return "", {}
    except Exception as exc:
        logger.debug("bs4 error for %s: %s", url, exc)
        return "", {}


# ── HTML metadata extraction ──────────────────────────────────────────────────

def _extract_html_meta(html: str, url: str) -> dict:
    """Extract metadata from OpenGraph, Twitter Card, and JSON-LD."""
    meta: dict = {}
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")

        # OpenGraph
        og_map = {
            "og:title": "title",
            "og:url": "canonical_url",
            "og:article:published_time": "publication_date",
            "og:article:modified_time": "modified_date",
            "og:article:author": "author",
        }
        for prop, key in og_map.items():
            tag = soup.find("meta", property=prop)
            if tag and tag.get("content"):
                meta[key] = tag["content"]

        # Twitter Card
        tc_map = {"twitter:title": "title"}
        for name, key in tc_map.items():
            tag = soup.find("meta", attrs={"name": name})
            if tag and tag.get("content") and not meta.get(key):
                meta[key] = tag["content"]

        # Standard meta
        for name_attr in ("author", "article:author"):
            tag = soup.find("meta", attrs={"name": name_attr})
            if tag and tag.get("content") and not meta.get("author"):
                meta["author"] = tag["content"]

        # Canonical link
        canon = soup.find("link", rel="canonical")
        if canon and canon.get("href") and not meta.get("canonical_url"):
            meta["canonical_url"] = canon["href"]

        # JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    data = data[0]
                if isinstance(data, dict) and data.get("@type") in (
                    "NewsArticle", "Article", "WebPage"
                ):
                    if not meta.get("title"):
                        meta["title"] = data.get("headline") or data.get("name")
                    if not meta.get("publication_date"):
                        meta["publication_date"] = _clean_date(
                            data.get("datePublished")
                        )
                    if not meta.get("modified_date"):
                        meta["modified_date"] = _clean_date(data.get("dateModified"))
                    if not meta.get("author"):
                        author = data.get("author")
                        if isinstance(author, dict):
                            meta["author"] = author.get("name")
                        elif isinstance(author, list) and author:
                            meta["author"] = author[0].get("name") if isinstance(author[0], dict) else str(author[0])
                        elif isinstance(author, str):
                            meta["author"] = author
            except Exception:
                continue

        # Clean dates
        for date_field in ("publication_date", "modified_date"):
            if meta.get(date_field):
                meta[date_field] = _clean_date(meta[date_field])

    except ImportError:
        pass
    except Exception as exc:
        logger.debug("HTML meta extraction error: %s", exc)

    return meta


# ── Helpers ───────────────────────────────────────────────────────────────────

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _clean_date(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    m = _DATE_RE.search(str(raw))
    return m.group(1) if m else None
