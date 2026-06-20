# Food Oil Adulteration News Crawler

A focused, modular news-crawling pipeline for collecting Indian news articles
about **edible oil adulteration** from the last 5 years.

Built for the **Food Computing** research project, which compares news-reported
adulteration incidents with FSSAI survey data and maps extracted information to
a food ontology.

---

## Project Purpose

This crawler collects, filters, deduplicates, and stores news articles covering:

- Edible oil adulteration incidents in India
- FSSAI / state food safety department actions
- Raids, seizures, arrests, and fines
- Lab test failures and consumer complaints
- Health and economic impacts of oil adulteration

Target oils: mustard oil, cooking oil, vegetable oil, palm oil, soybean oil,
groundnut oil, sesame oil, sunflower oil, cottonseed oil, blended oil, rice
bran oil, coconut oil.

---

## Repository Structure

```
news_crawler/
├── config/
│   ├── config.yaml          # all settings (date range, terms, thresholds)
│   ├── queries.yaml         # pre-built high/medium/supplementary queries
│   └── sources.yaml         # target domains, RSS feeds, blocked domains
├── data/
│   ├── seeds/
│   │   └── seed_urls.csv    # 12 seed URLs from oil_sample_articles.docx
│   ├── raw_html/            # downloaded HTML (auto-organised by domain)
│   ├── cleaned_text/        # extracted article text files
│   ├── outputs/
│   │   ├── articles.db      # SQLite database (primary store)
│   │   ├── articles.jsonl   # JSONL export
│   │   ├── articles.csv     # CSV export
│   │   ├── discovered_urls.jsonl
│   │   └── report.json
│   └── logs/
│       └── crawler.log
├── crawler/
│   ├── __init__.py
│   ├── __main__.py          # python -m crawler entry point
│   ├── config.py            # Config class
│   ├── query_builder.py     # search query generation
│   ├── storage.py           # SQLite + JSONL + CSV storage
│   ├── downloader.py        # polite HTTP downloader
│   ├── extractor.py         # article text extraction
│   ├── relevance.py         # rule-based relevance scoring
│   ├── dedupe.py            # deduplication (URL, title, hash, near-dup)
│   ├── report.py            # run summary reporter
│   ├── cli.py               # Click CLI
│   └── discovery/
│       ├── __init__.py
│       ├── seed_loader.py   # loads seed URLs from docx and CSV
│       ├── gdelt.py         # GDELT Doc 2.0 API (free, no key needed)
│       ├── rss.py           # RSS/Atom feed polling
│       └── search_api.py    # Google CSE / Bing / SerpAPI (optional)
├── tests/
│   ├── test_query_builder.py
│   ├── test_relevance.py
│   ├── test_dedupe.py
│   ├── test_extractor.py
│   └── test_storage.py
├── notebooks/               # Jupyter notebooks for analysis
├── requirements.txt
├── .env.example
└── README.md                # this file
```

---

## Setup

### 1. Install Python 3.10+

### 2. Create a virtual environment

```bash
cd news_crawler
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys (optional)

```bash
cp .env.example .env
# Edit .env with your keys (Google CSE, Bing, SerpAPI)
```

Without API keys, the crawler will use:
- Seed URLs from `oil_sample_articles.docx` and `data/seeds/seed_urls.csv`
- GDELT API (free, no key required)
- RSS feeds from 20+ Indian news sources

---

## Configuration

All settings live in `config/config.yaml`. Key sections:

| Section | What it controls |
|---|---|
| `date_range` | `start` and `end` dates for filtering |
| `food_terms` | Oil/food terms to search and score |
| `adulteration_terms` | Incident terms (fake, spurious, substandard…) |
| `action_terms` | Enforcement terms (FSSAI, seized, raid…) |
| `location_terms` | Indian states and cities |
| `crawl` | `delay_seconds`, `max_retries`, `timeout_seconds` |
| `discovery.enabled_sources` | Which backends to use |
| `relevance` | Score thresholds and weights |
| `dedupe` | Toggle each dedup layer |
| `paths` | Override all output directory paths |

To change the time range, edit:

```yaml
date_range:
  start: "2021-06-01"
  end: "2026-06-17"
```

---

## Adding Seed URLs

Edit `data/seeds/seed_urls.csv`. Required column: `url`. Optional columns:
`title_snippet`, `domain`, `published_date`, `query_used`, `notes`.

The `oil_sample_articles.docx` file is auto-detected from the parent directory
and its URLs are loaded automatically via the seed loader.

---

## Running the Pipeline

All commands are run from the `news_crawler/` directory.

### Run each stage individually

```bash
# 1. Discover candidate URLs
python -m crawler discover --config config/config.yaml

# 2. Download HTML
python -m crawler crawl --config config/config.yaml

# 3. Extract article text
python -m crawler extract --config config/config.yaml

# 4. Score and label by relevance
python -m crawler filter --config config/config.yaml

# 5. Detect and mark duplicates
python -m crawler dedupe --config config/config.yaml

# 6. Export to CSV/JSONL
python -m crawler export --config config/config.yaml --format all

# 7. Print run report
python -m crawler report --config config/config.yaml
```

### Run the full pipeline at once

```bash
python -m crawler run-all --config config/config.yaml
```

### Limit the number of articles per stage (for testing)

```bash
python -m crawler crawl --config config/config.yaml --limit 50
```

### Verbose logging

```bash
python -m crawler --verbose discover --config config/config.yaml
```

### Use specific discovery sources

```bash
python -m crawler discover --sources seed --sources gdelt
```

---

## Running Tests

```bash
cd news_crawler
pytest tests/ -v
# With coverage
pytest tests/ --cov=crawler --cov-report=term-missing
```

Tests cover:
- Query generation (no duplicates, correct content)
- Relevance scoring (12 seed articles should score ≥ maybe_relevant)
- URL normalisation (tracking params stripped, www normalised)
- Deduplication (exact URL, normalised title, text hash, near-duplicate)
- Storage (CRUD operations, JSON serialisation, CSV/JSONL export)
- HTML metadata extraction (OpenGraph, JSON-LD, canonical URL)

---

## Output Schema

### Main articles table (SQLite + JSONL + CSV)

| Field | Type | Description |
|---|---|---|
| `article_id` | UUID | Primary key |
| `title` | text | Article headline |
| `url` | text | Original URL |
| `canonical_url` | text | Normalised URL |
| `source` | text | Publication name |
| `domain` | text | Hostname |
| `author` | text | Author name if available |
| `publication_date` | date | YYYY-MM-DD |
| `discovered_at` | datetime | When URL was first found |
| `crawled_at` | datetime | When HTML was downloaded |
| `query_used` | text | Query that found this URL |
| `discovery_method` | text | seed / gdelt / rss / google_cse / bing / serpapi |
| `raw_html_path` | path | Path to saved raw HTML |
| `cleaned_text_path` | path | Path to cleaned text file |
| `article_text` | text | Full cleaned article body |
| `food_terms_found` | JSON list | Oil terms matched in text |
| `adulteration_terms_found` | JSON list | Incident terms matched |
| `action_terms_found` | JSON list | Enforcement terms matched |
| `location_terms_found` | JSON list | India location terms matched |
| `relevance_score` | float 0–1 | Weighted relevance score |
| `relevance_label` | text | `relevant` / `maybe_relevant` / `irrelevant` |
| `duplicate_cluster_id` | UUID | Groups duplicate articles |
| `is_duplicate` | bool | True if flagged as duplicate |
| `duplicate_of_url` | text | Primary article URL |
| `extraction_status` | text | `success` / `partial` / `failed` |
| `extraction_method` | text | `trafilatura` / `newspaper` / `beautifulsoup` |
| `text_hash` | SHA-256 | Used for exact deduplication |
| `word_count` | int | Words in cleaned text |
| `nlp_*` | various | Placeholder fields for NLP extraction stage |

### NLP extraction fields (prepared for future pipeline stage)

| Field | Description |
|---|---|
| `nlp_oil_type` | Specific oil type mentioned |
| `nlp_adulterant` | What the oil was mixed with |
| `nlp_adulteration_type` | Type of adulteration |
| `nlp_quantity` | Volume/weight seized |
| `nlp_location_city/district/state` | Location of incident |
| `nlp_incident_type` | raid / seizure / lab_failure / complaint / etc. |
| `nlp_action_taken` | Arrests / fines / licence cancellation |
| `nlp_fssai_category` | FSSAI regulation category |
| `nlp_ontology_mapping` | Food ontology concept IDs |

---

## Relevance Scoring Logic

### Layer 1: Rule-based (always runs)

Score is accumulated from 0.0 to 1.0:

| Component | Max contribution |
|---|---|
| Oil/food terms found in text | 0.30 |
| Adulteration terms found | 0.25 |
| Enforcement/action terms found | 0.20 |
| India location terms found | 0.15 |
| Publication date in configured range | 0.10 |

**Hard filters** (configurable, all enabled by default):
- Must contain at least one Indian location term or FSSAI
- Must contain at least one oil/food term
- Must contain at least one adulteration OR enforcement term

**Hard rejections** (not configurable):
- Recipe pages
- Commodity price / futures market articles
- "How to check purity" guides
- E-commerce / buy-online pages

### Labels

| Label | Score threshold |
|---|---|
| `relevant` | ≥ 0.55 |
| `maybe_relevant` | ≥ 0.25 |
| `irrelevant` | < 0.25 |

### Layer 2: Zero-shot LLM (stub)

`RelevanceScorer.classify_zero_shot()` is a stub. To activate:
- Wire in a HuggingFace `zero-shot-classification` pipeline
- Or call Claude/GPT API with the article text and the label set

---

## Ethical Crawling Notes

- **robots.txt is always checked** (configurable via `crawl.respect_robots_txt`)
- **Crawl delay** of 2.5 seconds between requests (configurable)
- **User-agent** identifies the bot as academic research
- **No Google SERP scraping** — uses GDELT API, RSS feeds, or official search APIs
- **Rate limiting** via exponential backoff on failures
- GDELT API terms ask for reasonable use; queries are batched and spaced

---

## Next Steps: NLP Extraction

The pipeline prepares `nlp_*` fields for a downstream extraction stage:

1. **Named Entity Recognition** — extract location, organisation, person names
2. **Relation extraction** — link oil type → adulterant → quantity → location
3. **Zero-shot classification** — confirm relevance label with an LLM
4. **Ontology mapping** — map `oil_type` and `adulterant` to FoodOn / ENVO concepts
5. **FSSAI categorisation** — align with FSSAI product categories and FSS regulations

Example integration point (`crawler/relevance.py`):
```python
scorer.classify_zero_shot(article_text)
# returns one of:
# 'relevant_edible_oil_adulteration_incident'
# 'general_food_safety'
# 'recipe_consumer_advice'
# 'commodity_price'
# 'unrelated'
```
