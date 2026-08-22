"""Crawl sample article URLs from the DOCX and extract keyword candidates.

This script is intentionally run-scoped. It reads URLs from the sample DOCX,
downloads those pages fresh, extracts text with the existing crawler extractor,
and derives keyword candidates only from the newly extracted article text.
It does not read previous crawler outputs, seed CSVs, or Media Cloud.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawler.config import BASE_DIR, Config
from crawler.downloader import Downloader
from crawler.extractor import Extractor


URL_RE = re.compile(r"https?://[^\s\"'<>]+")
WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9&/-]*")

STOPWORDS = {
    "a", "about", "after", "again", "against", "all", "also", "am", "an",
    "and", "any", "are", "as", "at", "be", "been", "being", "between",
    "both", "but", "by", "can", "could", "did", "do", "does", "doing",
    "down", "during", "each", "few", "for", "from", "further", "had",
    "has", "have", "having", "he", "her", "here", "hers", "him", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "just", "more",
    "most", "no", "nor", "not", "now", "of", "off", "on", "once", "only",
    "or", "other", "our", "out", "over", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "would",
    "you", "your", "said", "says", "new", "news", "story", "article",
    "photo", "photos", "video", "read", "updated", "published", "reported",
}

PRODUCT_TERMS = [
    "edible oil", "cooking oil", "mustard oil", "palm oil", "soybean oil",
    "sunflower oil", "groundnut oil", "coconut oil", "rice bran oil",
    "cottonseed oil", "sesame oil", "vegetable oil", "refined oil",
    "loose oil", "loose edible oil",
]

ADULTERATION_TERMS = [
    "adulterated", "adulteration", "substandard", "spurious", "fake",
    "counterfeit", "misbranded", "contaminated", "unsafe", "fraud",
    "rancid", "reused oil", "recycled oil", "rotten", "mixed with",
]

ENFORCEMENT_TERMS = [
    "fssai", "fda", "food safety", "food safety department",
    "food safety officer", "raid", "raids", "seized", "seizure",
    "samples collected", "sample collected", "samples sent", "lab test",
    "quality test", "prosecution", "licence suspended", "license suspended",
    "shop sealed", "warehouse", "godown", "arrested", "crackdown",
    "inspection", "ban", "banned", "fine", "penalty",
]

LOCATION_TERMS = [
    "india", "andhra pradesh", "arunachal pradesh", "assam", "bihar",
    "chhattisgarh", "delhi", "goa", "gujarat", "haryana",
    "himachal pradesh", "jharkhand", "karnataka", "kerala",
    "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "up", "uttarakhand",
    "west bengal", "hyderabad", "pokaran", "barabanki",
    "thiruvananthapuram", "kanpur", "noida", "jaipur",
]

CATEGORY_TERMS = {
    "oil/product": PRODUCT_TERMS,
    "adulteration/fraud": ADULTERATION_TERMS,
    "enforcement/evidence": ENFORCEMENT_TERMS,
    "location": LOCATION_TERMS,
}

METHODS = ("phrase_frequency", "tfidf", "yake")
COMPOSITE_WEIGHTS = {
    "tfidf": 0.35,
    "yake": 0.25,
    "frequency": 0.15,
    "document_frequency": 0.15,
    "method_agreement": 0.10,
}

NON_OIL_FOOD_TERMS = {
    "paneer", "mawa", "tea", "ice cream", "ice creams", "milk", "dates",
    "wheat", "namkeen", "sweets", "bakery", "meat", "sauce", "sauces",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docx",
        default=str(BASE_DIR.parent / "oil_sample_articles.docx"),
        help="Sample DOCX containing article URLs.",
    )
    parser.add_argument(
        "--run-dir",
        default=str(BASE_DIR / "data" / "runs" / "edible_oils_from_sample_2026-06-21"),
        help="Fresh run folder for all outputs.",
    )
    parser.add_argument(
        "--config",
        default=str(BASE_DIR / "config" / "config.yaml"),
        help="Base crawler config. Only crawler settings and term lists are reused.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit URLs for testing. 0 means all URLs.",
    )
    parser.add_argument(
        "--playwright-fallback",
        action="store_true",
        help="Allow browser fallback if requests extraction fails.",
    )
    parser.add_argument(
        "--keywords-only",
        action="store_true",
        help="Regenerate clean keyword scoring from this run folder without crawling.",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(exist_ok=True)
    _setup_logging(run_dir / "logs" / "sample_crawl_keywords.log")

    if args.keywords_only:
        article_rows, keyword_docs = load_existing_sample_articles(run_dir)
        summary = write_keyword_outputs(
            run_dir=run_dir,
            docs=keyword_docs,
            article_rows=article_rows,
            docx_path=Path(args.docx),
            urls_from_docx=None,
            mode="keywords_only",
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    urls = extract_urls_from_docx(Path(args.docx))
    if args.limit:
        urls = urls[: args.limit]
    write_url_manifest(urls, run_dir / "source_urls_from_docx.csv")

    cfg = Config(args.config)
    _override_paths(cfg, run_dir, use_playwright=args.playwright_fallback)

    downloader = Downloader(cfg)
    extractor = Extractor(cfg)
    article_rows = []
    keyword_docs = []

    try:
        for idx, url in enumerate(urls, start=1):
            logging.info("Fetching %s/%s: %s", idx, len(urls), url)
            download = downloader.download(url)
            extraction = {}
            if download.get("status") == "success" and download.get("raw_html"):
                extraction = extractor.extract(
                    download.get("url") or url,
                    download["raw_html"],
                    raw_html_path=download.get("raw_html_path"),
                )
            else:
                extraction = {
                    "url": url,
                    "domain": urlparse(url).netloc.removeprefix("www."),
                    "title": None,
                    "publication_date": None,
                    "article_text": None,
                    "extraction_status": "failed",
                    "extraction_method": None,
                    "error_message": download.get("error_message"),
                    "raw_html_path": download.get("raw_html_path"),
                    "cleaned_text_path": None,
                    "word_count": 0,
                }

            text = extraction.get("article_text") or ""
            title = extraction.get("title") or ""
            row = {
                "article_number": idx,
                "url": download.get("url") or url,
                "original_url": url,
                "domain": extraction.get("domain") or urlparse(url).netloc.removeprefix("www."),
                "title": title,
                "source": extraction.get("domain") or urlparse(url).netloc.removeprefix("www."),
                "date": extraction.get("publication_date") or "",
                "download_status": download.get("status"),
                "http_status": download.get("http_status") or "",
                "extraction_status": extraction.get("extraction_status"),
                "extraction_method": extraction.get("extraction_method") or "",
                "word_count": extraction.get("word_count") or 0,
                "raw_html_path": extraction.get("raw_html_path") or "",
                "cleaned_text_path": extraction.get("cleaned_text_path") or "",
                "error_message": extraction.get("error_message") or download.get("error_message") or "",
                "first_2_lines": first_lines(text, 2),
            }
            article_rows.append(row)
            if text:
                keyword_docs.append(
                    {
                        "article_number": idx,
                        "title": title or f"Article {idx}",
                        "url": row["url"],
                        "domain": row["domain"],
                        "text": text,
                    }
                )
    finally:
        downloader.close()

    write_csv(run_dir / "sample_articles.csv", article_rows)
    write_jsonl(run_dir / "sample_articles.jsonl", article_rows)
    write_corpus(run_dir / "sample_corpus.txt", keyword_docs)

    summary = write_keyword_outputs(
        run_dir=run_dir,
        docs=keyword_docs,
        article_rows=article_rows,
        docx_path=Path(args.docx),
        urls_from_docx=len(urls),
        mode="crawl_and_keywords",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _setup_logging(path: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def _override_paths(cfg: Config, run_dir: Path, use_playwright: bool) -> None:
    paths = cfg.raw.setdefault("paths", {})
    paths["raw_html"] = str(run_dir / "raw_html")
    paths["cleaned_text"] = str(run_dir / "cleaned_text")
    crawl = cfg.raw.setdefault("crawl", {})
    crawl["use_playwright"] = bool(use_playwright)


def extract_urls_from_docx(docx_path: Path) -> list[str]:
    try:
        import docx  # type: ignore
    except ImportError as exc:
        raise RuntimeError("python-docx is required to read the sample DOCX") from exc

    doc = docx.Document(str(docx_path))
    seen = set()
    urls = []
    for para in doc.paragraphs:
        for url in URL_RE.findall(para.text):
            clean = url.rstrip(".,;)")
            if clean not in seen:
                seen.add(clean)
                urls.append(clean)
    return urls


def write_url_manifest(urls: list[str], path: Path) -> None:
    rows = [
        {
            "article_number": idx,
            "url": url,
            "domain": urlparse(url).netloc.removeprefix("www."),
        }
        for idx, url in enumerate(urls, start=1)
    ]
    write_csv(path, rows)


def load_existing_sample_articles(run_dir: Path) -> tuple[list[dict], list[dict]]:
    article_path = run_dir / "sample_articles.jsonl"
    if not article_path.exists():
        raise FileNotFoundError(f"Missing sample article table: {article_path}")

    article_rows = []
    docs = []
    with article_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            article_rows.append(row)
            text_path = Path(row.get("cleaned_text_path") or "")
            if row.get("extraction_status") not in {"success", "partial"}:
                continue
            if not text_path.exists():
                logging.warning("Missing cleaned text for article %s: %s", row.get("article_number"), text_path)
                continue
            text = text_path.read_text(encoding="utf-8")
            if text.strip():
                docs.append(
                    {
                        "article_number": int(row["article_number"]),
                        "title": row.get("title") or f"Article {row['article_number']}",
                        "url": row.get("url") or "",
                        "domain": row.get("domain") or "",
                        "text": text,
                    }
                )
    return article_rows, docs


def write_keyword_outputs(
    run_dir: Path,
    docs: list[dict],
    article_rows: list[dict],
    docx_path: Path,
    urls_from_docx: int | None,
    mode: str,
) -> dict:
    candidates = extract_keyword_candidates(docs)
    keyword_csv = run_dir / "sample_keyword_candidates_clean.csv"
    keyword_jsonl = run_dir / "sample_keyword_candidates_clean.jsonl"
    write_csv(keyword_csv, candidates)
    write_jsonl(keyword_jsonl, candidates)

    label_counts = Counter(row["review_label"] for row in candidates)
    category_counts = Counter(row["category"] for row in candidates)
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "docx": str(docx_path.resolve()),
        "run_dir": str(run_dir),
        "urls_from_docx": urls_from_docx if urls_from_docx is not None else "",
        "download_success": sum(1 for r in article_rows if r.get("download_status") == "success"),
        "extraction_success_or_partial": sum(
            1 for r in article_rows if r.get("extraction_status") in {"success", "partial"}
        ),
        "keyword_source_articles": len(docs),
        "keyword_candidates_clean": len(candidates),
        "review_label_counts": dict(sorted(label_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "scoring": {
            "candidate_creation_methods": list(METHODS),
            "reference_lexicon_use": "categorization_only",
            "composite_weights": COMPOSITE_WEIGHTS,
            "review_labels": ["keep_core", "manual_review", "drop"],
        },
        "outputs": {
            "url_manifest": str(run_dir / "source_urls_from_docx.csv"),
            "article_table": str(run_dir / "sample_articles.csv"),
            "article_jsonl": str(run_dir / "sample_articles.jsonl"),
            "corpus": str(run_dir / "sample_corpus.txt"),
            "keyword_table_clean": str(keyword_csv),
            "keyword_jsonl_clean": str(keyword_jsonl),
            "log": str(run_dir / "logs" / "sample_crawl_keywords.log"),
        },
    }
    (run_dir / "sample_keyword_clean_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def extract_keyword_candidates(docs: list[dict]) -> list[dict]:
    candidate_map: dict[str, dict] = {}

    for phrase, count in phrase_frequency_candidates(docs).items():
        add_candidate(candidate_map, phrase, "phrase_frequency", score=float(count))

    for phrase, score in tfidf_candidates(docs).items():
        add_candidate(candidate_map, phrase, "tfidf", score=score)

    for phrase, score in yake_candidates(docs).items():
        add_candidate(candidate_map, phrase, "yake", score=score)

    max_method_scores = {
        method: max(
            (data["method_scores"].get(method, 0.0) for data in candidate_map.values()),
            default=0.0,
        )
        for method in METHODS
    }
    max_total_frequency = max(
        (count_phrase(phrase, docs) for phrase in candidate_map),
        default=0,
    )
    doc_count = max(len(docs), 1)

    rows = []
    for phrase, data in candidate_map.items():
        example = find_example(phrase, docs)
        category = categorize(phrase)
        total_frequency = count_phrase(phrase, docs)
        document_frequency = count_documents_phrase(phrase, docs)
        method_count = len(data["methods"])
        method_agreement_score = method_count / len(METHODS)
        tfidf_score_normalized = normalize(
            data["method_scores"].get("tfidf", 0.0),
            max_method_scores["tfidf"],
        )
        yake_score_normalized = normalize(
            data["method_scores"].get("yake", 0.0),
            max_method_scores["yake"],
        )
        frequency_score_normalized = normalize(total_frequency, max_total_frequency)
        document_frequency_score = document_frequency / doc_count
        composite_score = (
            COMPOSITE_WEIGHTS["tfidf"] * tfidf_score_normalized
            + COMPOSITE_WEIGHTS["yake"] * yake_score_normalized
            + COMPOSITE_WEIGHTS["frequency"] * frequency_score_normalized
            + COMPOSITE_WEIGHTS["document_frequency"] * document_frequency_score
            + COMPOSITE_WEIGHTS["method_agreement"] * method_agreement_score
        )
        review_label, review_reason = assign_review_label(
            phrase=phrase,
            category=category,
            composite_score=composite_score,
            method_count=method_count,
            document_frequency=document_frequency,
            total_frequency=total_frequency,
        )
        rows.append(
            {
                "keyword_or_keyphrase": phrase,
                "methods_found": "; ".join(sorted(data["methods"])),
                "method_count": method_count,
                "method_agreement_score": round(method_agreement_score, 6),
                "total_frequency": total_frequency,
                "document_frequency": document_frequency,
                "tfidf_score_normalized": round(tfidf_score_normalized, 6),
                "yake_score_normalized": round(yake_score_normalized, 6),
                "frequency_score_normalized": round(frequency_score_normalized, 6),
                "document_frequency_score": round(document_frequency_score, 6),
                "composite_score": round(composite_score, 6),
                "category": category,
                "review_label": review_label,
                "review_reason": review_reason,
                "example_article_number": example.get("article_number", ""),
                "example_article_title": example.get("title", ""),
                "example_url": example.get("url", ""),
                "example_context": example_context(phrase, example),
            }
        )

    rows.sort(
        key=lambda r: (
            {"keep_core": 0, "manual_review": 1, "drop": 2}.get(r["review_label"], 3),
            -float(r["composite_score"] or 0),
            -int(r["total_frequency"] or 0),
            str(r["keyword_or_keyphrase"]),
        )
    )
    return rows


def add_candidate(
    candidate_map: dict[str, dict],
    phrase: str,
    method: str,
    score: float | None = None,
) -> None:
    phrase = clean_phrase(phrase)
    if not phrase or len(phrase) < 3:
        return
    if is_bad_phrase(phrase):
        return
    data = candidate_map.setdefault(
        phrase,
        {"methods": set(), "method_scores": {}},
    )
    data["methods"].add(method)
    if score is not None:
        data["method_scores"][method] = max(
            data["method_scores"].get(method, 0.0),
            float(score),
        )


def phrase_frequency_candidates(docs: list[dict], top_n: int = 120) -> Counter:
    counts: Counter = Counter()
    for doc in docs:
        tokens = [
            t.lower()
            for t in WORD_RE.findall(doc["text"])
            if not is_stop_token(t.lower())
        ]
        for n in range(1, 5):
            for i in range(0, len(tokens) - n + 1):
                phrase = " ".join(tokens[i : i + n])
                if n == 1 and not is_domainish(phrase):
                    continue
                if is_bad_phrase(phrase):
                    continue
                if is_domainish(phrase) or n >= 2:
                    counts[phrase] += 1
    return Counter(dict(counts.most_common(top_n)))


def tfidf_candidates(docs: list[dict], top_n: int = 80) -> dict[str, float]:
    if not docs:
        return {}
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    except ImportError:
        logging.info("scikit-learn not installed; skipping TF-IDF extraction")
        return {}

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words=list(STOPWORDS),
        ngram_range=(1, 4),
        min_df=1,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9&/-]+\b",
    )
    matrix = vectorizer.fit_transform([d["text"] for d in docs])
    sums = matrix.sum(axis=0).A1
    features = vectorizer.get_feature_names_out()
    ranked = sorted(zip(features, sums), key=lambda item: item[1], reverse=True)
    out = {}
    for phrase, score in ranked:
        phrase = clean_phrase(phrase)
        if is_bad_phrase(phrase):
            continue
        if is_domainish(phrase) or len(phrase.split()) >= 2:
            out[phrase] = float(score)
        if len(out) >= top_n:
            break
    return out


def yake_candidates(docs: list[dict], top_n: int = 80) -> dict[str, float]:
    if not docs:
        return {}
    try:
        import yake  # type: ignore
    except ImportError:
        logging.info("YAKE not installed; skipping YAKE extraction")
        return {}

    text = "\n\n".join(d["text"] for d in docs)
    extractor = yake.KeywordExtractor(lan="en", n=4, dedupLim=0.75, top=top_n)
    out = {}
    for phrase, raw_score in extractor.extract_keywords(text):
        phrase = clean_phrase(phrase)
        if is_bad_phrase(phrase):
            continue
        # YAKE lower scores are better; invert for easier sorting with others.
        out[phrase] = 1.0 / (1.0 + float(raw_score))
    return out


def categorize(phrase: str) -> str:
    p = phrase.lower()
    matching = []
    for category, terms in CATEGORY_TERMS.items():
        if any(re.search(boundary_pattern(term), p, flags=re.I) for term in terms):
            matching.append(category)
    if len(matching) > 1:
        return "incident/action phrase"
    if matching:
        return matching[0]
    return "other_candidate"


def find_example(phrase: str, docs: list[dict]) -> dict:
    pattern = boundary_pattern(phrase)
    for doc in docs:
        if re.search(pattern, doc["text"], flags=re.I):
            return doc
    return {}


def count_phrase(phrase: str, docs: list[dict]) -> int:
    pattern = boundary_pattern(phrase)
    return sum(len(re.findall(pattern, doc["text"], flags=re.I)) for doc in docs)


def count_documents_phrase(phrase: str, docs: list[dict]) -> int:
    pattern = boundary_pattern(phrase)
    return sum(1 for doc in docs if re.search(pattern, doc["text"], flags=re.I))


def normalize(value: float | int, max_value: float | int) -> float:
    if not max_value:
        return 0.0
    return float(value) / float(max_value)


def assign_review_label(
    phrase: str,
    category: str,
    composite_score: float,
    method_count: int,
    document_frequency: int,
    total_frequency: int,
) -> tuple[str, str]:
    drop_reason = quality_drop_reason(phrase, category)
    if drop_reason:
        return "drop", drop_reason

    if category == "location":
        return "manual_review", "location term; useful only if we decide to add geography-specific queries"

    if is_ghee_only(phrase):
        return "manual_review", "ghee can drift into dairy; keep only if you want oil-and-ghee coverage"

    if category == "oil/product":
        if has_oil_signal(phrase) and composite_score >= 0.35:
            return "keep_core", "clear edible-oil product term found in sample text"
        return "manual_review", "food/product term is relevant but not strong enough alone"

    if category == "incident/action phrase":
        if composite_score >= 0.40 and (has_oil_signal(phrase) or method_count >= 2):
            return "keep_core", "combined product/adulteration/enforcement phrase"
        return "manual_review", "incident/action phrase needs human pruning"

    if category in {"adulteration/fraud", "enforcement/evidence"}:
        if composite_score >= 0.45 and (method_count >= 2 or document_frequency >= 2 or total_frequency >= 3):
            return "keep_core", "strong domain term for combining with oil-product terms"
        if composite_score >= 0.20 or method_count >= 2:
            return "manual_review", "domain term is plausible but weaker or too broad"
        return "drop", "weak domain term below threshold"

    if method_count >= 2 and composite_score >= 0.45:
        return "manual_review", "statistically strong phrase but not in edible-oil categories"

    return "drop", "low score or outside edible-oil/adulteration scope"


def quality_drop_reason(phrase: str, category: str) -> str:
    p = phrase.lower()
    tokens = p.split()
    if len(tokens) > 6:
        return "too long for a seed keyword"
    if tokens and tokens[0] in {"time", "credits", "source", "sources"}:
        return "boilerplate or incomplete phrase"
    if re.search(r"\b(canva|etimes|copyright|advertisement|newsletter)\b", p):
        return "page boilerplate"
    if contains_non_oil_food_context(p) and not has_oil_signal(p):
        return "non-oil food context without edible-oil signal"
    if category == "other_candidate" and not is_domainish(p):
        return "outside edible-oil/adulteration domain"
    return ""


def has_oil_signal(phrase: str) -> bool:
    p = phrase.lower()
    return any(
        term in p
        for term in (
            "oil", "edible", "cooking", "mustard", "palm", "soybean",
            "sunflower", "groundnut", "coconut", "rice bran", "cottonseed",
            "sesame", "vegetable oil", "refined",
        )
    )


def is_ghee_only(phrase: str) -> bool:
    p = phrase.lower()
    return "ghee" in p and not has_oil_signal(p)


def contains_non_oil_food_context(phrase: str) -> bool:
    p = phrase.lower()
    return any(term in p for term in NON_OIL_FOOD_TERMS)


def example_context(phrase: str, doc: dict, window: int = 110) -> str:
    text = doc.get("text") or ""
    if not text:
        return ""
    match = re.search(boundary_pattern(phrase), text, flags=re.I)
    if not match:
        return ""
    start = max(match.start() - window, 0)
    end = min(match.end() + window, len(text))
    context = re.sub(r"\s+", " ", text[start:end]).strip()
    if start > 0:
        context = "..." + context
    if end < len(text):
        context += "..."
    return context


def boundary_pattern(phrase: str) -> str:
    escaped = re.escape(phrase.strip())
    escaped = escaped.replace(r"\ ", r"\s+")
    return rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"


def clean_phrase(phrase: str) -> str:
    phrase = re.sub(r"\s+", " ", phrase or "").strip(" -_:;,.()[]{}\"'").lower()
    return phrase


def is_stop_token(token: str) -> bool:
    return token in STOPWORDS or len(token) < 3 or token.isdigit()


def is_bad_phrase(phrase: str) -> bool:
    tokens = phrase.split()
    if not tokens:
        return True
    if any(len(t) > 35 for t in tokens):
        return True
    if tokens[0] in STOPWORDS or tokens[-1] in STOPWORDS:
        return True
    if all(t in STOPWORDS for t in tokens):
        return True
    if re.search(r"https?|www|\.com|copyright|advertisement|subscribe", phrase):
        return True
    return False


def is_domainish(phrase: str) -> bool:
    p = phrase.lower()
    return any(
        term in p
        for term in (
            "oil", "adulter", "fake", "spurious", "substandard", "misbrand",
            "fssai", "fda", "raid", "seiz", "food safety", "sample",
            "coconut", "mustard", "edible", "cooking", "vegetable",
            "fraud", "ban", "crackdown",
        )
    )


def first_lines(text: str, n: int) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " / ".join(lines[:n])


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_corpus(path: Path, docs: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for doc in docs:
            fh.write(f"\n\n===== ARTICLE {doc['article_number']}: {doc['title']} =====\n")
            fh.write(f"URL: {doc['url']}\n\n")
            fh.write(doc["text"])


if __name__ == "__main__":
    raise SystemExit(main())
