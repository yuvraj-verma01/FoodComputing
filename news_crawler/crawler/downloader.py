"""HTTP downloader with optional Playwright fallback for JS-rendered pages."""

from __future__ import annotations

import hashlib
import logging
import re
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter

from .config import Config

logger = logging.getLogger(__name__)

# Cache of RobotFileParser objects (one per domain)
_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


class Downloader:
    """Downloads pages one at a time, politely.

    Features:
    - Configurable robots.txt compliance (respect_robots_txt in config)
    - Playwright browser fallback for SSL failures and JS-rendered pages
    - Configurable crawl delay, exponential backoff, retries
    - Raw HTML saved to disk
    """

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.raw_html_dir = cfg.path("raw_html")
        self.delay = cfg.crawl_delay
        self.timeout = int(cfg.get("crawl", "timeout_seconds") or 30)
        self.max_retries = int(cfg.get("crawl", "max_retries") or 3)
        self.backoff_factor = float(cfg.get("crawl", "backoff_factor") or 2.0)
        self.respect_robots = bool(cfg.get("crawl", "respect_robots_txt") is not False)
        self.use_playwright = cfg.get("crawl", "use_playwright") is not False
        self.playwright_first = bool(cfg.get("crawl", "playwright_first") is True)
        self._session = self._build_session()
        self._pw = None        # lazy playwright instance
        self._browser = None

    # ------------------------------------------------------------------

    def download(self, url: str) -> dict:
        """Download *url* and return a result dict.

        Keys:
            url, status (success|failed|robots_blocked|skipped),
            raw_html, raw_html_path, http_status, error_message,
            content_type, downloaded_at
        """
        result: dict = {
            "url": url,
            "status": "failed",
            "raw_html": None,
            "raw_html_path": None,
            "http_status": None,
            "error_message": None,
            "content_type": None,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }

        is_gnews_redirect = "news.google.com" in url

        if self.respect_robots and not is_gnews_redirect and not self._allowed_by_robots(url):
            result["status"] = "robots_blocked"
            result["error_message"] = "Blocked by robots.txt"
            logger.info("robots.txt blocks %s", url)
            return result

        if self.use_playwright and self.playwright_first:
            pw_result = self._download_via_playwright(url, result)
            if pw_result["status"] == "success":
                return pw_result
            result = pw_result

        # Try requests first
        for attempt in range(1, self.max_retries + 2):
            try:
                resp = self._session.get(url, timeout=self.timeout)
                if is_gnews_redirect and resp.url != url and "news.google.com" not in resp.url:
                    result["url"] = resp.url
                    url = resp.url
                result["http_status"] = resp.status_code
                result["content_type"] = resp.headers.get("Content-Type", "")

                if resp.status_code == 200:
                    html = resp.text
                    result["raw_html"] = html
                    result["raw_html_path"] = str(self._save_html(url, html))
                    result["status"] = "success"
                    logger.debug("Downloaded %s (%d chars)", url, len(html))
                    time.sleep(self.delay)
                    return result
                elif resp.status_code in {301, 302, 303, 307, 308}:
                    result["status"] = "failed"
                    result["error_message"] = f"HTTP {resp.status_code}"
                    break
                elif resp.status_code in {403, 404, 410, 451}:
                    result["status"] = "failed"
                    result["error_message"] = f"HTTP {resp.status_code}"
                    break
                else:
                    result["error_message"] = f"HTTP {resp.status_code}"
                    logger.warning("HTTP %d for %s (attempt %d)", resp.status_code, url, attempt)

            except requests.exceptions.SSLError as exc:
                result["error_message"] = f"SSLError: {exc}"
                logger.info("SSL error on %s — trying Playwright", url)
                break
            except requests.exceptions.Timeout:
                result["error_message"] = "Timeout"
                logger.warning("Timeout on %s (attempt %d)", url, attempt)
            except requests.exceptions.ConnectionError as exc:
                result["error_message"] = f"ConnectionError: {exc}"
                logger.warning("Connection error on %s (attempt %d): %s", url, attempt, exc)
            except Exception as exc:
                result["error_message"] = str(exc)
                logger.warning("Unexpected error on %s (attempt %d): %s", url, attempt, exc)
                break

            if attempt <= self.max_retries:
                time.sleep(self.backoff_factor ** attempt)

        # Playwright fallback for SSL errors and other failures
        if self.use_playwright and result["status"] == "failed":
            return self._download_via_playwright(url, result)

        time.sleep(0.5)
        return result

    # ------------------------------------------------------------------

    def _download_via_playwright(self, url: str, result: dict) -> dict:
        """Fetch page using a headless Chromium browser via Playwright."""
        try:
            browser = self._get_browser()
        except Exception as exc:
            logger.warning("Playwright unavailable: %s", exc)
            return result

        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
                locale="en-US",
                timezone_id="Asia/Kolkata",
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = context.new_page()
            page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
                "Upgrade-Insecure-Requests": "1",
            })

            response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            # Let dynamic content settle briefly
            page.wait_for_timeout(1500)

            html = self._read_playwright_html(page, response)
            final_url = page.url
            http_status = response.status if response else 200

            context.close()

            if http_status in {404, 410, 451}:
                result["status"] = "failed"
                result["error_message"] = f"HTTP {http_status} (playwright)"
                result["http_status"] = http_status
            elif html and len(html) > 500:
                result["url"] = final_url
                result["http_status"] = http_status
                result["raw_html"] = html
                result["raw_html_path"] = str(self._save_html(final_url, html))
                result["status"] = "success"
                result["error_message"] = None
                logger.info("Playwright fetched %s (%d chars)", final_url, len(html))
                time.sleep(self.delay)
            else:
                result["error_message"] = "Playwright: empty page"

        except Exception as exc:
            logger.warning("Playwright failed on %s: %s", url, exc)
            result["error_message"] = f"Playwright: {exc}"

        return result

    def _read_playwright_html(self, page, response) -> str:
        """Read rendered HTML even when the page keeps navigating after load."""
        for _ in range(3):
            try:
                return page.content()
            except Exception:
                try:
                    page.wait_for_timeout(1000)
                except Exception:
                    break

        try:
            html = page.evaluate("document.documentElement.outerHTML")
            if html:
                return html
        except Exception:
            pass

        if response is not None:
            try:
                return response.text()
            except Exception:
                pass
        return ""

    def _get_browser(self):
        """Lazily start the Playwright Chromium browser (one shared instance)."""
        if self._browser is not None:
            return self._browser
        from playwright.sync_api import sync_playwright  # type: ignore
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        logger.info("Playwright Chromium browser started")
        return self._browser

    # ------------------------------------------------------------------

    def _allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in _robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(urljoin(base, "/robots.txt"))
            try:
                rp.read()
            except Exception:
                _robots_cache[base] = None  # type: ignore
                return True
            _robots_cache[base] = rp

        rp = _robots_cache.get(base)
        if rp is None:
            return True
        return rp.can_fetch(self.cfg.user_agent, url)

    def _save_html(self, url: str, html: str) -> Path:
        """Save raw HTML to data/raw_html/<domain>/<url_hash>.html."""
        parsed = urlparse(url)
        domain = parsed.netloc.removeprefix("www.")
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        domain_dir = self.raw_html_dir / _safe_dirname(domain)
        domain_dir.mkdir(parents=True, exist_ok=True)
        path = domain_dir / f"{url_hash}.html"
        path.write_text(html, encoding="utf-8")
        return path

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.cfg.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "DNT": "1",
        })
        adapter = HTTPAdapter(max_retries=0)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def close(self) -> None:
        self._session.close()
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_dirname(name: str) -> str:
    """Make a filesystem-safe directory name from a domain."""
    return re.sub(r"[^\w\-.]", "_", name)
