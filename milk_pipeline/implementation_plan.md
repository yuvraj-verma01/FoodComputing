# Milk Adulteration Pipeline - Implementation Plan

This document outlines the proposed implementation for your milk adulteration article extraction pipeline, starting from January 1, 2021. 

The current workspace contains a very well-structured skeleton for an iterative extraction pipeline (extract -> query -> fetch -> filter -> repeat). However, all core modules currently raise `NotImplementedError`. 

Here is the plan to build out your desired flow.

## User Review Required

> [!IMPORTANT]
> The current keyword extraction stubs assume the use of `YAKE` (where lower scores = more relevant). We will be switching to `KeyBERT`, which uses cosine similarity (where **higher** scores = more relevant). The ranking logic must be reversed throughout the pipeline.

> [!WARNING]
> Media Cloud and GDELT have different query syntax and API constraints. 
> - **Media Cloud** generally requires an API key and uses Solr query syntax. 
> - **GDELT** (e.g., using the DOC 2.0 API) does not strictly require an API key but has specific syntax and strict rate limiting.

## Open Questions

> [!IMPORTANT]
> 1. **Media Cloud Access:** Do you already have an active Media Cloud API key?
> 2. **Seed Document Format:** The `milk_sample_articles.docx` contains your 20 seed articles. What format is the data in the document? (e.g., just a list of URLs, or full text and titles?) If it's URLs, we'll need to scrape them first; if it's text, we just need to parse the docx.
> 3. **Manual vs Automated Filtering:** The current codebase implements automated rule-based filtering (e.g., checking if an article contains at least 2 distinct seed keywords). Do you want to start with this automated rule, or do you want to inject a manual review step between rounds?

## Proposed Changes

### Seed Extraction

Currently, the pipeline expects seeds in `seeds/seed_articles.json`. We will write a script to parse `milk_sample_articles.docx`.

#### [NEW] [parse_seeds.py](file:///c:/Myself/milk_pipeline/parse_seeds.py)
- Use `python-docx` to read the `.docx` file.
- Extract the 20 seed articles (either parsing full text or extracting URLs to scrape).
- Save the structured output to `seeds/seed_articles.json`.

---

### Keyword Extraction (KeyBERT)

#### [MODIFY] [pipeline/extract_keywords.py](file:///c:/Myself/milk_pipeline/pipeline/extract_keywords.py)
- **Library:** Install and use `keybert` (which uses `sentence-transformers`).
- **Implementation:** Concatenate the title and text of the articles and use `KeyBERT().extract_keywords()`.
- **Ranking:** Sort keywords in descending order (highest similarity score first).
- **Merge Logic:** Combine keywords from previous rounds with new ones, keeping the top `N` based on KeyBERT similarity scores.

---

### Query Building & Fetching

#### [MODIFY] [pipeline/build_query.py](file:///c:/Myself/milk_pipeline/pipeline/build_query.py)
- Implement query builders that support AND/OR/NOT logic.
- **Media Cloud:** Generate a Solr-compliant query string, grouping phrases in quotes.
- **GDELT:** Generate a GDELT DOC API compliant query string.
- Automatically inject the date constraint (`>= 2021-01-01`).

#### [MODIFY] [pipeline/fetch_articles.py](file:///c:/Myself/milk_pipeline/pipeline/fetch_articles.py)
- **Libraries:** Use `requests` to call the APIs.
- Make parallel or sequential calls to Media Cloud and GDELT.
- Implement exponential backoff for 429 (Rate Limit) and 5xx (Server) errors.
- Parse responses into a unified dictionary format (`url`, `title`, `text`, `publish_date`).

---

### Filtering & Orchestration

#### [MODIFY] [pipeline/filter_relevance.py](file:///c:/Myself/milk_pipeline/pipeline/filter_relevance.py)
- **`filter_keywords`**: Implement a blocklist check to drop boilerplate keywords (e.g., "police said").
- **`score_article`**: Count how many seed keywords exist in the fetched article's body. Return this score so the orchestrator can decide if it meets the `MIN_KEYWORD_MATCHES` threshold.

#### [MODIFY] [run_pipeline.py](file:///c:/Myself/milk_pipeline/run_pipeline.py)
- Wire up the actual function calls to the modified pipeline modules.
- Ensure the `date_from` argument is explicitly passed as `2021-01-01` to the fetch module.
- Manage the iterative loop, ending when 0 new articles are found.

#### [MODIFY] [pipeline/scrape_fulltext.py](file:///c:/Myself/milk_pipeline/pipeline/scrape_fulltext.py) & [pipeline/dedup.py](file:///c:/Myself/milk_pipeline/pipeline/dedup.py)
- Implement `trafilatura` for full-text scraping of articles that only returned snippets from the APIs.
- Implement URL normalization and exact title matching to deduplicate the final combined dataset.

## Verification Plan

### Automated Tests
- Create a dummy test for `extract_keywords.py` with mock text to verify KeyBERT is installed and returns valid keywords sorted correctly.
- Test `build_query.py` by printing the generated Media Cloud and GDELT query strings for a given keyword list.

### Manual Verification
- We will first run the pipeline for just **Round 1** with a strict `MAX_RESULTS_PER_QUERY` (e.g., 50) and review the `round_1_filtered/filtered_results.json` dataset to confirm relevance.
- You can manually inspect the fetched keywords in the logs before we scale up to infinite iteration loops.
