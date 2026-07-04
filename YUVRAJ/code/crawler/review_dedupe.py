from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORTS_DIR = ROOT / "reports"
DEFAULT_MASTER_DIR = DEFAULT_REPORTS_DIR / "master_corpus"

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
    "utm",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or parts.path
    query_items = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower in TRACKING_QUERY_PARAMS:
            continue
        if any(key_lower.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        query_items.append((key, value))
    query = urlencode(sorted(query_items))
    return urlunsplit((scheme, netloc, path, query, ""))


def url_keys(url: str) -> set[str]:
    raw = (url or "").strip()
    normalized = normalized_url(raw)
    return {key for key in {raw, normalized} if key}


def is_human_marked(row: dict[str, str]) -> bool:
    for col in (
        "final_keep",
        "human_keep",
        "review_keep",
        "keep",
        "final_decision",
        "final_decisio",
    ):
        if str(row.get(col, "")).strip() in {"0", "1"}:
            return True
    for col in ("final_human_label", "human_label"):
        if str(row.get(col, "")).strip().lower() in {"relevant", "irrelevant"}:
            return True
    return False


def load_reviewed_url_keys(
    master_dir: Path = DEFAULT_MASTER_DIR,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
) -> set[str]:
    keys: set[str] = set()
    candidate_paths: list[Path] = [
        master_dir / "master_all_round_articles.csv",
        master_dir / "master_all_articles.csv",
        master_dir / "master_duplicate_label_conflicts.csv",
    ]
    if not any(path.exists() for path in candidate_paths):
        candidate_paths.extend(
            sorted(reports_dir.glob("edible_oil_adulteration_round_*/round_*_all_articles.csv"))
        )

    for path in candidate_paths:
        if not path.exists():
            continue
        for row in read_csv(path):
            url = row.get("url", "")
            if url and is_human_marked(row):
                keys.update(url_keys(url))
    return keys


def split_new_review_rows(
    rows: list[dict[str, str]],
    reviewed_url_keys: set[str],
    url_column: str = "url",
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    new_rows: list[dict[str, str]] = []
    already_reviewed: list[dict[str, str]] = []
    for row in rows:
        if url_keys(row.get(url_column, "")) & reviewed_url_keys:
            already_reviewed.append(row)
        else:
            new_rows.append(row)
    return new_rows, already_reviewed
