"""Retry failed discovered URLs with Playwright enabled.

This intentionally skips URLs blocked by robots.txt. It is for pages that failed
because of SSL, JavaScript rendering, transient HTTP, or similar fetch issues.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crawler.config import Config  # noqa: E402
from crawler.downloader import Downloader  # noqa: E402
from crawler.storage import Storage  # noqa: E402


DEFAULT_CONFIG = ROOT / "config" / "config_edible_oils_from_sample.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cfg = Config(args.config)
    cfg.raw.setdefault("crawl", {})["use_playwright"] = True
    cfg.raw.setdefault("crawl", {})["respect_robots_txt"] = True

    storage = Storage(cfg)
    downloader = Downloader(cfg)
    sql = "SELECT * FROM discovered_urls WHERE status='failed' ORDER BY id"
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    failed = [dict(row) for row in storage.conn.execute(sql).fetchall()]

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": str(args.config),
        "attempted": len(failed),
        "success": 0,
        "robots_blocked": 0,
        "failed": 0,
        "details": [],
    }

    for rec in failed:
        url = rec["url"]
        result = downloader.download(url)
        status = result.get("status") or "failed"
        resolved_url = result.get("url") or url
        storage.mark_discovered_status(url, status)

        if status == "success":
            summary["success"] += 1
            storage.save_article(
                {
                    "url": resolved_url,
                    "canonical_url": resolved_url,
                    "domain": rec.get("domain"),
                    "source": rec.get("source"),
                    "query_used": rec.get("query_used"),
                    "discovery_method": rec.get("discovery_method"),
                    "raw_html_path": result.get("raw_html_path"),
                    "extraction_status": "pending",
                    "discovered_at": rec.get("discovered_at"),
                }
            )
        elif status == "robots_blocked":
            summary["robots_blocked"] += 1
        else:
            summary["failed"] += 1

        summary["details"].append(
            {
                "url": url,
                "resolved_url": resolved_url,
                "status": status,
                "http_status": result.get("http_status"),
                "error_message": result.get("error_message"),
            }
        )

    downloader.close()
    storage.close()

    out_path = cfg.path("outputs") / "playwright_failed_retry_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
