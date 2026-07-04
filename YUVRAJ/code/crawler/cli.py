"""Command-line interface for the Food Oil News Crawler.

Usage examples:
    python -m crawler discover --config config/config.yaml
    python -m crawler crawl    --config config/config.yaml
    python -m crawler extract  --config config/config.yaml
    python -m crawler filter   --config config/config.yaml
    python -m crawler dedupe   --config config/config.yaml
    python -m crawler run-all  --config config/config.yaml
    python -m crawler export   --config config/config.yaml --format csv
    python -m crawler report   --config config/config.yaml
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Optional

import click

from .config import Config
from .dedupe import Deduplicator
from .discovery import DDGSDiscovery, GDELTDiscovery, GoogleNewsDiscovery, MediaCloudDiscovery, RSSDiscovery, SearchAPIDiscovery, SeedLoader
from .keyword_augmentor import KeywordAugmentor
from .downloader import Downloader
from .extractor import Extractor
from .query_builder import generate_queries
from .relevance import RelevanceScorer, url_looks_relevant
from .report import Reporter
from .storage import Storage

logger = logging.getLogger(__name__)


def _get_feedparser():
    try:
        import feedparser  # type: ignore
        return feedparser
    except ImportError:
        raise SystemExit("feedparser not installed. Run: pip install feedparser")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Also log to file
    # (log path will be set up after config is loaded)


# ── CLI root ──────────────────────────────────────────────────────────────────

@click.group()
@click.option("--config", "-c", default="config/config.yaml", show_default=True,
              help="Path to config.yaml")
@click.option("--verbose", "-v", is_flag=True, default=False)
@click.pass_context
def cli(ctx: click.Context, config: str, verbose: bool) -> None:
    """Food Oil Adulteration News Crawler."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    cfg = Config(config)
    ctx.obj["cfg"] = cfg
    # File handler
    log_dir = cfg.path("logs")
    fh = logging.FileHandler(log_dir / "crawler.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(fh)


# ── discover ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--sources", "-s", multiple=True,
              help="Override enabled sources (seed, gdelt, rss, google_news, ddgs, google_cse, bing, serpapi)")
@click.pass_context
def discover(ctx: click.Context, sources: tuple) -> None:
    """Discover candidate URLs from all enabled backends."""
    cfg: Config = ctx.obj["cfg"]
    storage = Storage(cfg)
    enabled = list(sources) or cfg.get("discovery", "enabled_sources") or ["seed"]

    queries = generate_queries(cfg)
    click.echo(f"Generated {len(queries)} queries.")

    total_new = 0

    if "seed" in enabled:
        click.echo("Loading seed URLs...")
        loader = SeedLoader(cfg)
        for rec in loader.discover():
            if url_looks_relevant(rec["url"], rec.get("title_snippet") or ""):
                if storage.save_discovered(rec):
                    total_new += 1

    if "gdelt" in enabled:
        click.echo(f"Querying GDELT ({len(queries)} queries)...")
        gdelt = GDELTDiscovery(cfg)
        with click.progressbar(queries, label="GDELT") as bar:
            for q in bar:
                for rec in gdelt._search(q):
                    if url_looks_relevant(rec["url"], rec.get("title_snippet") or ""):
                        if storage.save_discovered(rec):
                            total_new += 1
                time.sleep(cfg.crawl_delay)
        gdelt.close()

    if "rss" in enabled:
        click.echo("Polling RSS feeds...")
        rss = RSSDiscovery(cfg)
        for rec in rss.discover():
            if url_looks_relevant(rec["url"], rec.get("title_snippet") or ""):
                if storage.save_discovered(rec):
                    total_new += 1

    if "google_news" in enabled:
        click.echo(f"Querying Google News RSS ({len(queries)} queries)...")
        gnews = GoogleNewsDiscovery(cfg)
        with click.progressbar(queries, label="Google News") as bar:
            for q in bar:
                for rec in gnews._search(q, _get_feedparser()):
                    if url_looks_relevant(rec["url"], rec.get("title_snippet") or ""):
                        if storage.save_discovered(rec):
                            total_new += 1
                time.sleep(gnews.delay)
        gnews.close()

    if "ddgs" in enabled:
        click.echo(f"Querying DuckDuckGo News ({len(queries)} queries)...")
        ddgs_disc = DDGSDiscovery(cfg)
        try:
            from ddgs import DDGS as _DDGS  # type: ignore
            _ddg = _DDGS()
        except ImportError:
            raise SystemExit("ddgs not installed. Run: pip install ddgs")
        with click.progressbar(queries, label="DuckDuckGo") as bar:
            for q in bar:
                for rec in ddgs_disc._search(_ddg, q):
                    if url_looks_relevant(rec["url"], rec.get("title_snippet") or ""):
                        if storage.save_discovered(rec):
                            total_new += 1
                time.sleep(ddgs_disc.delay)
        ddgs_disc.close()

    if any(s in enabled for s in ("google_cse", "bing", "serpapi")):
        click.echo("Querying search APIs...")
        search = SearchAPIDiscovery(cfg)
        for rec in search.discover(queries):
            if url_looks_relevant(rec["url"], rec.get("title_snippet") or ""):
                if storage.save_discovered(rec):
                    total_new += 1
        search.close()

    counts = storage.count_discovered()
    click.echo(f"\nDiscovery complete. New URLs: {total_new}")
    click.echo(f"Pending: {counts.get('pending', 0)}  |  Total: {sum(counts.values())}")
    storage.close()


# ── crawl ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--limit", "-n", default=0, type=int,
              help="Max articles to download (0 = all pending)")
@click.pass_context
def crawl(ctx: click.Context, limit: int) -> None:
    """Download HTML for all pending discovered URLs."""
    cfg: Config = ctx.obj["cfg"]
    storage = Storage(cfg)
    downloader = Downloader(cfg)
    scorer = RelevanceScorer(cfg)

    pending = storage.get_pending_urls(limit=limit)
    click.echo(f"Downloading {len(pending)} URLs...")

    success = failed = blocked = 0

    with click.progressbar(pending, label="Crawling") as bar:
        for url_rec in bar:
            url = url_rec["url"]
            result = downloader.download(url)
            status = result["status"]

            # resolved_url may differ from original if a Google News redirect was followed
            resolved_url = result.get("url", url)
            storage.mark_discovered_status(url, status)

            if status == "success":
                success += 1
                html = result.get("raw_html", "") or ""
                # Save a minimal article record; extract step will fill in text
                article = {
                    "url": resolved_url,
                    "canonical_url": resolved_url,
                    "domain": url_rec.get("domain"),
                    "source": url_rec.get("source"),
                    "query_used": url_rec.get("query_used"),
                    "discovery_method": url_rec.get("discovery_method"),
                    "raw_html_path": result.get("raw_html_path"),
                    "extraction_status": "pending",
                    "discovered_at": url_rec.get("discovered_at"),
                }
                storage.save_article(article)
            elif status == "robots_blocked":
                blocked += 1
            else:
                failed += 1

    click.echo(f"\nDownload complete. Success: {success}  Blocked: {blocked}  Failed: {failed}")
    downloader.close()
    storage.close()


# ── extract ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--limit", "-n", default=0, type=int)
@click.pass_context
def extract(ctx: click.Context, limit: int) -> None:
    """Extract article text from downloaded raw HTML files."""
    cfg: Config = ctx.obj["cfg"]
    storage = Storage(cfg)
    extractor = Extractor(cfg)

    # Get articles where raw_html_path is set but text not extracted
    sql = "SELECT * FROM articles WHERE extraction_status='pending' AND raw_html_path IS NOT NULL"
    if limit:
        sql += f" LIMIT {limit}"
    rows = storage.conn.execute(sql).fetchall()
    articles = [dict(r) for r in rows]
    click.echo(f"Extracting text for {len(articles)} articles...")

    success = failed = 0
    with click.progressbar(articles, label="Extracting") as bar:
        for art in bar:
            url = art["url"]
            raw_path = art.get("raw_html_path")
            try:
                html = Path(raw_path).read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                storage.update_article(url, {
                    "extraction_status": "failed",
                    "error_message": f"Cannot read HTML: {exc}",
                })
                failed += 1
                continue

            result = extractor.extract(url, html, raw_html_path=raw_path)
            updates = {k: v for k, v in result.items() if k != "url"}
            storage.update_article(url, updates)

            if result["extraction_status"] == "success":
                success += 1
            else:
                failed += 1

    click.echo(f"\nExtraction complete. Success: {success}  Failed: {failed}")
    storage.close()


# ── filter ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--limit", "-n", default=0, type=int)
@click.pass_context
def filter_articles(ctx: click.Context, limit: int) -> None:
    """Score and label articles by relevance."""
    cfg: Config = ctx.obj["cfg"]
    storage = Storage(cfg)
    scorer = RelevanceScorer(cfg)

    sql = "SELECT * FROM articles WHERE relevance_label IS NULL AND article_text IS NOT NULL"
    if limit:
        sql += f" LIMIT {limit}"
    rows = [dict(r) for r in storage.conn.execute(sql).fetchall()]
    click.echo(f"Scoring {len(rows)} articles...")

    counts: dict[str, int] = {}
    with click.progressbar(rows, label="Filtering") as bar:
        for art in bar:
            res = scorer.score(
                text=art.get("article_text") or "",
                title=art.get("title") or "",
                url=art.get("url") or "",
                publication_date=art.get("publication_date"),
            )
            import json as _json
            storage.update_article(art["url"], {
                "relevance_score": res.score,
                "relevance_label": res.label,
                "food_terms_found": _json.dumps(res.food_terms_found),
                "adulteration_terms_found": _json.dumps(res.adulteration_terms_found),
                "action_terms_found": _json.dumps(res.action_terms_found),
                "location_terms_found": _json.dumps(res.location_terms_found),
            })
            counts[res.label] = counts.get(res.label, 0) + 1

    click.echo("\nRelevance distribution:")
    for label, n in sorted(counts.items()):
        click.echo(f"  {label}: {n}")
    storage.close()


# ── dedupe ────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def dedupe(ctx: click.Context) -> None:
    """Detect and mark duplicate articles."""
    cfg: Config = ctx.obj["cfg"]
    storage = Storage(cfg)
    deduplicator = Deduplicator(cfg)

    click.echo("Loading existing articles into deduplicator index...")
    # Process articles ordered by publication date descending (keep newest as primary)
    rows = list(storage.conn.execute(
        "SELECT * FROM articles ORDER BY publication_date DESC NULLS LAST, crawled_at DESC"
    ).fetchall())
    articles = [dict(r) for r in rows]
    click.echo(f"Processing {len(articles)} articles...")

    dup_count = 0
    for art in articles:
        is_dup, dup_of = deduplicator.check(art)
        if is_dup and dup_of:
            cluster_id = deduplicator.assign_cluster(art["article_id"], dup_of)
            storage.update_article(art["url"], {
                "is_duplicate": 1,
                "duplicate_of_url": storage.get_article(
                    next(
                        (a["url"] for a in articles if a["article_id"] == dup_of),
                        art["url"],
                    )
                ) and storage.get_article(
                    next(
                        (a["url"] for a in articles if a["article_id"] == dup_of),
                        art["url"],
                    )
                ).get("url"),
                "duplicate_cluster_id": cluster_id,
            })
            dup_count += 1
        else:
            cluster_id = deduplicator.register(art)
            if not art.get("duplicate_cluster_id"):
                storage.update_article(art["url"], {"duplicate_cluster_id": cluster_id})

    click.echo(f"Deduplication complete. Duplicates marked: {dup_count}")
    storage.close()


# ── export ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--format", "-f", "fmt",
              type=click.Choice(["csv", "jsonl", "sqlite", "all"], case_sensitive=False),
              default="all", show_default=True)
@click.option("--output", "-o", default=None, help="Override output path")
@click.pass_context
def export(ctx: click.Context, fmt: str, output: Optional[str]) -> None:
    """Export articles to CSV / JSONL."""
    cfg: Config = ctx.obj["cfg"]
    storage = Storage(cfg)

    if fmt in ("csv", "all"):
        path = storage.export_csv(Path(output) if output else None)
        click.echo(f"CSV export: {path}")

    if fmt in ("jsonl", "all"):
        path = storage.export_jsonl(Path(output) if output else None)
        click.echo(f"JSONL export: {path}")

    if fmt in ("sqlite", "all"):
        click.echo(f"SQLite DB: {cfg.path('db')}")

    storage.close()


# ── report ────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def report(ctx: click.Context) -> None:
    """Print and save a pipeline run summary report."""
    cfg: Config = ctx.obj["cfg"]
    storage = Storage(cfg)
    reporter = Reporter(cfg, storage)
    r = reporter.build()
    reporter.save(r)
    reporter.print_summary(r)
    storage.close()


# ── run-all ───────────────────────────────────────────────────────────────────

@cli.command("run-all")
@click.option("--limit", "-n", default=0, type=int,
              help="Max articles per stage (0 = unlimited)")
@click.pass_context
def run_all(ctx: click.Context, limit: int) -> None:
    """Run the full pipeline: discover > crawl > extract > filter > dedupe > report."""
    click.echo("=== STAGE 1: DISCOVER ===")
    ctx.invoke(discover)
    click.echo("\n=== STAGE 2: CRAWL ===")
    ctx.invoke(crawl, limit=limit)
    click.echo("\n=== STAGE 3: EXTRACT ===")
    ctx.invoke(extract, limit=limit)
    click.echo("\n=== STAGE 4: FILTER ===")
    ctx.invoke(filter_articles, limit=limit)
    click.echo("\n=== STAGE 5: DEDUPE ===")
    ctx.invoke(dedupe)
    click.echo("\n=== STAGE 6: EXPORT ===")
    ctx.invoke(export, fmt="all", output=None)
    click.echo("\n=== STAGE 7: REPORT ===")
    ctx.invoke(report)


# ── mc-collections ────────────────────────────────────────────────────────────

@cli.command("mc-collections")
@click.option("--filter", "-f", "name_filter", default="india",
              help="Filter collections by name (default: india)")
@click.pass_context
def mc_collections(ctx: click.Context, name_filter: str) -> None:
    """List Media Cloud collections matching a name filter.

    Use this to find the collection IDs to put in config_mediacloud.yaml.
    Requires MEDIACLOUD_API_KEY in .env.
    """
    cfg: Config = ctx.obj["cfg"]
    try:
        mc = MediaCloudDiscovery(cfg)
    except ValueError as exc:
        raise SystemExit(str(exc))

    click.echo(f"Searching Media Cloud collections for '{name_filter}'...")
    collections = mc.list_collections(name_filter)
    if not collections:
        click.echo("No collections found. Check your API key and filter term.")
        return
    click.echo(f"\nFound {len(collections)} collection(s):\n")
    for col in collections:
        col_id = col.get("id") or col.get("collection_id") or "?"
        name = (col.get("name") or col.get("label") or "Unknown").encode("ascii", "replace").decode("ascii")
        source_count = col.get("source_count") or col.get("media_count") or "?"
        click.echo(f"  [{col_id}]  {name}  ({source_count} sources)")
    click.echo(
        "\nAdd the desired IDs to config_mediacloud.yaml under "
        "discovery.mediacloud.collection_ids"
    )


# ── mc-discover ───────────────────────────────────────────────────────────────

@cli.command("mc-discover")
@click.option("--round", "-r", "round_num", default=0, type=int,
              help="Augmentation round number (0 = seed keywords)")
@click.pass_context
def mc_discover(ctx: click.Context, round_num: int) -> None:
    """Discover articles from Media Cloud for one augmentation round.

    Run mc-augment to execute all rounds automatically, or use this
    command to run a single round manually followed by crawl + extract.

    Round 0 uses seed keywords. Later rounds use keywords extracted from
    articles collected in previous rounds.
    """
    cfg: Config = ctx.obj["cfg"]
    storage = Storage(cfg)
    augmentor = KeywordAugmentor(cfg)

    try:
        mc = MediaCloudDiscovery(cfg)
    except ValueError as exc:
        raise SystemExit(str(exc))

    queries = augmentor.get_queries_for_round(round_num)
    click.echo(
        f"Round {round_num}: {len(queries)} quer{'y' if len(queries)==1 else 'ies'} -> Media Cloud"
    )
    if round_num > 0:
        click.echo(f"Keywords from previous round: {queries[:5]}{'...' if len(queries)>5 else ''}")

    total_new = 0
    with click.progressbar(queries, label=f"  Round {round_num}") as bar:
        for q in bar:
            for rec in mc._search(mc._get_client(), q):
                if url_looks_relevant(rec["url"], rec.get("title_snippet") or ""):
                    if storage.save_discovered(rec):
                        total_new += 1

    counts = storage.count_discovered()
    click.echo(f"\nMedia Cloud discovery complete. New URLs: {total_new}")
    click.echo(f"Pending: {counts.get('pending',0)}  |  Total: {sum(counts.values())}")

    # Persist round info to augmentor state
    augmentor.record_round(round_num, queries, total_new)
    augmentor.save_state()

    storage.close()
    mc.close()


# ── mc-augment ────────────────────────────────────────────────────────────────

@cli.command("mc-augment")
@click.option("--max-rounds", default=0, type=int,
              help="Override max rounds (0 = use config value)")
@click.option("--resume", is_flag=True, default=False,
              help="Resume from last completed round instead of starting fresh")
@click.option("--dry-run", is_flag=True, default=False,
              help="Print planned queries without hitting the API")
@click.pass_context
def mc_augment(ctx: click.Context, max_rounds: int, resume: bool, dry_run: bool) -> None:
    """Run the full iterative keyword augmentation pipeline.

    Algorithm:
      Round 0 -- seed keywords -> Media Cloud -> article URLs -> crawl -> extract
      Round 1 -- extract keywords from articles -> new queries -> Media Cloud -> ...
      ...repeat until convergence or max_rounds reached

    Requires MEDIACLOUD_API_KEY in .env.
    Requires: pip install mediacloud yake scikit-learn
    """
    cfg: Config = ctx.obj["cfg"]
    storage = Storage(cfg)
    augmentor = KeywordAugmentor(cfg)

    if max_rounds:
        augmentor.max_rounds = max_rounds

    # Dry-run: just print planned queries, no API needed
    if dry_run:
        for round_num in range(augmentor.max_rounds):
            queries = augmentor.get_queries_for_round(round_num)
            click.echo(f"\nRound {round_num} ({len(queries)} queries):")
            for q in queries:
                click.echo(f"  {q}")
            if round_num > 0:
                click.echo("  (subsequent round queries are derived from extracted keywords)")
                break
        storage.close()
        return

    extractor_obj = __import__("crawler.extractor", fromlist=["Extractor"]).Extractor(cfg)
    scorer = RelevanceScorer(cfg)

    try:
        mc = MediaCloudDiscovery(cfg)
    except ValueError as exc:
        raise SystemExit(str(exc))

    start_round = augmentor.current_round if resume else 0
    if not resume and augmentor.current_round > 0:
        click.echo(
            f"Warning: augmentation state exists (round {augmentor.current_round}). "
            "Use --resume to continue or delete data/outputs/augmentation_state.json to restart."
        )
        if not click.confirm("Start fresh anyway?", default=False):
            storage.close()
            return

    click.echo(f"\nStarting keyword augmentation from round {start_round}")
    click.echo(f"Max rounds: {augmentor.max_rounds}  |  Convergence threshold: {augmentor.convergence_threshold}")
    click.echo(f"State file: {augmentor.state_path}\n")

    for round_num in range(start_round, augmentor.max_rounds):
        queries = augmentor.get_queries_for_round(round_num)
        click.echo("-" * 60)
        click.echo(f"  Round {round_num}  ({len(queries)} queries)")
        click.echo("-" * 60)

        # ── Discovery ──────────────────────────────────────────────────────
        total_discovered = 0
        with click.progressbar(queries, label=f"  Discovering (round {round_num})") as bar:
            for q in bar:
                for rec in mc._search(mc._get_client(), q):
                    if url_looks_relevant(rec["url"], rec.get("title_snippet") or ""):
                        if storage.save_discovered(rec):
                            total_discovered += 1
        click.echo(f"  Discovered: {total_discovered} new URLs")

        # ── Crawl ──────────────────────────────────────────────────────────
        pending = storage.get_pending_urls()
        click.echo(f"  Crawling {len(pending)} pending URLs...")
        downloader = __import__("crawler.downloader", fromlist=["Downloader"]).Downloader(cfg)
        success = failed = blocked = 0
        with click.progressbar(pending, label="  Crawling") as bar:
            for url_rec in bar:
                url = url_rec["url"]
                result = downloader.download(url)
                status = result["status"]
                resolved_url = result.get("url", url)
                storage.mark_discovered_status(url, status)
                if status == "success":
                    success += 1
                    article = {
                        "url": resolved_url,
                        "canonical_url": resolved_url,
                        "domain": url_rec.get("domain"),
                        "source": url_rec.get("source"),
                        "query_used": url_rec.get("query_used"),
                        "discovery_method": url_rec.get("discovery_method"),
                        "raw_html_path": result.get("raw_html_path"),
                        "extraction_status": "pending",
                        "discovered_at": url_rec.get("discovered_at"),
                    }
                    storage.save_article(article)
                elif status == "robots_blocked":
                    blocked += 1
                else:
                    failed += 1
        downloader.close()
        click.echo(f"  Crawl: {success} success, {blocked} blocked, {failed} failed")

        # ── Extract ────────────────────────────────────────────────────────
        import json as _json
        from pathlib import Path as _Path

        pending_arts = [
            dict(r) for r in storage.conn.execute(
                "SELECT * FROM articles WHERE extraction_status='pending' AND raw_html_path IS NOT NULL"
            ).fetchall()
        ]
        click.echo(f"  Extracting {len(pending_arts)} articles...")
        extracted_texts = []
        for art in pending_arts:
            raw_path = art.get("raw_html_path")
            try:
                html = _Path(raw_path).read_text(encoding="utf-8", errors="replace")
            except Exception:
                storage.update_article(art["url"], {"extraction_status": "failed"})
                continue
            result = extractor_obj.extract(art["url"], html, raw_html_path=raw_path)
            updates = {k: v for k, v in result.items() if k != "url"}
            storage.update_article(art["url"], updates)
            if result["extraction_status"] == "success" and result.get("article_text"):
                # Score relevance immediately
                res = scorer.score(
                    text=result.get("article_text") or "",
                    title=result.get("title") or "",
                    url=art.get("url") or "",
                    publication_date=result.get("publication_date"),
                )
                storage.update_article(art["url"], {
                    "relevance_score": res.score,
                    "relevance_label": res.label,
                    "food_terms_found": _json.dumps(res.food_terms_found),
                    "adulteration_terms_found": _json.dumps(res.adulteration_terms_found),
                    "action_terms_found": _json.dumps(res.action_terms_found),
                    "location_terms_found": _json.dumps(res.location_terms_found),
                })
                extracted_texts.append(result["article_text"])

        click.echo(f"  Extracted {len(extracted_texts)} articles with text")

        # ── Keyword extraction ─────────────────────────────────────────────
        if round_num < augmentor.max_rounds - 1:
            # Collect all article texts so far for richer keyword extraction
            all_texts = [
                dict(r)["article_text"]
                for r in storage.conn.execute(
                    "SELECT article_text FROM articles WHERE article_text IS NOT NULL AND relevance_label != 'irrelevant'"
                ).fetchall()
                if dict(r)["article_text"]
            ]
            prev_keywords = set(augmentor.all_keywords)
            new_keywords = augmentor.extract_keywords_from_texts(all_texts, prev_keywords)
            click.echo(f"  New keywords extracted: {len(new_keywords)}")
            for kw in new_keywords[:10]:
                click.echo(f"    + {kw}")
            augmentor.record_round(round_num, new_keywords, total_discovered)
            augmentor.save_state()

            # Check convergence
            converged, jaccard = augmentor.check_convergence(round_num)
            click.echo(f"\n  Jaccard similarity with previous round: {jaccard:.3f}")
            if converged:
                click.echo(
                    f"  Converged at round {round_num} "
                    f"(threshold: {augmentor.convergence_threshold})"
                )
                break
            if not new_keywords:
                click.echo("  No new keywords found — stopping.")
                break
        else:
            augmentor.record_round(round_num, [], total_discovered)
            augmentor.save_state()

    # ── Final steps ────────────────────────────────────────────────────────────
    click.echo("\n" + "=" * 60)
    click.echo("  Running deduplication and export...")
    ctx.invoke(dedupe)
    ctx.invoke(export, fmt="all", output=None)
    click.echo("\n" + augmentor.summary())
    ctx.invoke(report)

    storage.close()
    mc.close()


# Register filter command under correct name
cli.add_command(filter_articles, name="filter")
