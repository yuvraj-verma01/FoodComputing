from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = ROOT / "data" / "runs" / "ghee_from_sample_2026-06-30"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill failed ghee sample article extractions through the Jina reader fallback."
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--only-failed", action="store_true", default=True)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def reader_url(url: str) -> str:
    return f"https://r.jina.ai/http://r.jina.ai/http://{url}"


def fetch_reader(url: str) -> str:
    headers = {
        "User-Agent": "FoodSafetyResearchBot/1.0 academic keyword extraction",
        "Accept": "text/markdown,text/plain,*/*",
    }
    response = requests.get(reader_url(url), headers=headers, timeout=60)
    response.raise_for_status()
    return response.text


def parse_reader_markdown(markdown: str) -> tuple[str, str, str]:
    title = ""
    published = ""
    body_lines: list[str] = []
    in_body = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("Title: "):
            title = line.removeprefix("Title: ").strip()
            continue
        if line.startswith("Published Time: "):
            published = line.removeprefix("Published Time: ").strip()
            continue
        if line.startswith("Markdown Content:"):
            in_body = True
            continue
        if not in_body:
            continue
        if skip_reader_line(line):
            continue
        body_lines.append(strip_markdown(line))
    body = "\n".join(line for line in body_lines if line).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    return title, published, body


def skip_reader_line(line: str) -> bool:
    if not line:
        return False
    low = line.lower()
    if low in {"advertisement", "read more", "also read"}:
        return True
    if low.startswith(("url source:", "published time:", "markdown content:")):
        return True
    if line.startswith(("![", "[![", "[](")):
        return True
    if re.search(r"\b(login|subscribe|newsletter|share this|follow us|copyright)\b", low):
        return True
    if re.search(r"\.(jpg|jpeg|png|webp|gif)\)", low):
        return True
    return False


def strip_markdown(line: str) -> str:
    line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
    line = re.sub(r"[*_`#>]+", "", line)
    return re.sub(r"\s+", " ", line).strip()


def enough_article_text(text: str) -> bool:
    target = text.lower()
    return len(text.split()) >= 35 and "ghee" in target


def first_lines(text: str, n: int = 2) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " / ".join(lines[:n])


def main() -> int:
    args = parse_args()
    jsonl_path = args.run_dir / "sample_articles.jsonl"
    csv_path = args.run_dir / "sample_articles.csv"
    raw_dir = args.run_dir / "raw_html" / "_reader_fallback"
    clean_dir = args.run_dir / "cleaned_text" / "_reader_fallback"
    raw_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(jsonl_path)
    filled = []
    failed = []
    for row in rows:
        if row.get("extraction_status") in {"success", "partial"}:
            continue
        url = row.get("url") or row.get("original_url") or ""
        if not url:
            continue
        try:
            markdown = fetch_reader(url)
            title, published, body = parse_reader_markdown(markdown)
            if not enough_article_text(body):
                raise RuntimeError("reader fallback returned insufficient ghee article text")
            article_number = row.get("article_number")
            stem = f"article_{article_number}_{urlparse(url).netloc.replace('.', '_')}"
            raw_path = raw_dir / f"{stem}.md"
            clean_path = clean_dir / f"{stem}.txt"
            raw_path.write_text(markdown, encoding="utf-8")
            clean_path.write_text(body, encoding="utf-8")

            row.update(
                {
                    "download_status": "success_reader_fallback",
                    "extraction_status": "success",
                    "extraction_method": "jina_reader_markdown",
                    "word_count": len(body.split()),
                    "title": title or row.get("title") or "",
                    "source": row.get("domain") or urlparse(url).netloc.removeprefix("www."),
                    "date": published or row.get("date") or "",
                    "raw_html_path": str(raw_path),
                    "cleaned_text_path": str(clean_path),
                    "error_message": "",
                    "first_2_lines": first_lines(body),
                }
            )
            filled.append(url)
        except Exception as exc:  # noqa: BLE001
            row["error_message"] = f"reader fallback failed: {exc}"
            failed.append({"url": url, "error": str(exc)})

    write_jsonl(jsonl_path, rows)
    write_csv(csv_path, rows)

    summary = {
        "filled_count": len(filled),
        "failed_count": len(failed),
        "filled_urls": filled,
        "failed": failed,
        "article_jsonl": str(jsonl_path),
        "article_csv": str(csv_path),
    }
    (args.run_dir / "reader_fallback_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
