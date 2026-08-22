# Handoff: Adapting the News Crawler for Ghee Adulteration

*Compiled 2026-06-30 for a new extraction round targeting ghee adulteration news,
to be implemented by Codex. This describes what already exists for edible oil and
what needs to change/be added for ghee.*

## 1. Project purpose

`news_crawler/` (repo root: `c:\Users\yuvra\OneDrive\Desktop\RAship\FoodComputing\news_crawler\`)
is a pipeline that discovers, crawls, extracts, deduplicates, and relevance-labels
Indian news articles about food adulteration, for a research project comparing
news-reported incidents against FSSAI survey data and mapping them to a food
ontology. It was built and tuned end-to-end for **edible oil** adulteration.
We now want to run the same machinery for **ghee** adulteration as a second,
parallel target food.

**Important — ghee was previously explicitly excluded from the oil corpus.**
`crawler/oil_relevance.py` has `OUT_OF_SCOPE_FOOD_TERMS = ["ghee", "vanaspati"]`
and any article whose only food signal is ghee/vanaspati is forced to
`irrelevant`. There is also a standalone cleanup script,
`scripts/remove_ghee_from_boolean_run.py`, that was run specifically to purge
ghee/vanaspati URLs out of an oil discovery run's SQLite queue. So: nothing
ghee-related exists in the current corpus by design — this is a clean slate,
not a subset to mine out of existing data.

## 2. Repo structure

```
news_crawler/
├── config/              # YAML configs: term lists, date range, discovery sources, query sets
├── crawler/             # Core pipeline modules + Click CLI (python -m crawler ...)
│   └── discovery/       # Discovery backends (MediaCloud, DDGS, GDELT, RSS, seed, search_api)
├── scripts/              # One-off / pipeline orchestration scripts (50+), incl. the
│                          # 5-stage oil relevance pipeline and round-management scripts
├── src/model_training/  # ML relevance classifier training (TF-IDF, embeddings, transformers, ensembles)
├── data/                # raw_html/, cleaned_text/, outputs/articles.db (SQLite), runs/ (per-round work dirs)
├── reports/              # master_corpus/ (final labelled CSVs), model_training*/ (classifier results)
├── tests/                # pytest unit tests
└── README.md
```

## 3. CLI (`python -m crawler <command>`, from `crawler/cli.py`)

| Command | Purpose |
|---|---|
| `discover --sources [seed\|gdelt\|rss\|ddgs\|google_cse\|bing\|serpapi]` | Find candidate URLs |
| `crawl [--limit N]` | Download raw HTML |
| `extract [--limit N]` | Pull article text (trafilatura → newspaper4k → BeautifulSoup) |
| `filter [--limit N]` | Rule-based relevance scoring/labelling |
| `dedupe` | URL/title/text-hash/near-duplicate dedup |
| `export --format [csv\|jsonl\|sqlite\|all]` | Export from SQLite |
| `report` | Run summary |
| `run-all` | Full pipeline in sequence |
| `mc-collections [--filter NAME]` | List Media Cloud collections (needs `MEDIACLOUD_API_KEY`) |
| `mc-discover --round N` | One round of Media Cloud discovery |
| `mc-augment [--max-rounds M] [--resume]` | Full iterative keyword-augmentation discovery loop |

All commands take `--config path/to/config.yaml` — **this is how you point the
same code at a different target food**: a `config_ghee_*.yaml` plus matching
seed-keyword/query files, run side-by-side with the oil configs.

## 4. Discovery backends (`crawler/discovery/`)

| Backend | Source | Notes |
|---|---|---|
| `mediacloud.py` | Media Cloud API | **Primary/recommended.** India National (collection 34412118) + State & Local (38379954). Needs `MEDIACLOUD_API_KEY` in `.env`. Auth header `Token {key}`, dates must be `datetime.date` objects. |
| `ddgs.py` | DuckDuckGo/Yahoo/Bing via `ddgs` package | Best no-key fallback, real URLs (no redirect wrappers) |
| `gdelt.py` | GDELT Doc 2.0 | Free, heavily rate-limited (429s common) |
| `rss.py` | 20+ Indian news RSS feeds | Returns ~0 for niche/specific topics |
| `seed_loader.py` | CSV/DOCX seed URLs | Manual seeding |
| `search_api.py` | Google CSE / Bing / SerpAPI | Optional, needs keys |
| `google_news.py` | Google News RSS | **Avoid** — redirect URLs resolve to a JS page that extraction can't read |

## 5. The oil relevance/keyword system — exact term lists to adapt

### 5.1 Discovery-stage terms (`config/config_mediacloud.yaml`, `config/config.yaml`)

Used to build search queries and for the lightweight rule-based `crawler/relevance.py`
scorer (0–1 weighted score: oil terms 0.30, adulteration terms 0.25, action terms 0.20,
location terms 0.15, date-in-range 0.10; thresholds: relevant ≥0.55, maybe_relevant ≥0.25).

- **food_terms (oil)**: edible oil, mustard oil, cooking oil, vegetable oil, palm oil,
  soybean oil, groundnut oil, sesame oil, sunflower oil, cottonseed oil, blended oil,
  rice bran oil, coconut oil, refined oil, crude palm oil, loose oil, sarson tel,
  rapeseed oil, linseed oil
- **adulteration_terms**: adulteration, adulterated, fake, spurious, substandard,
  misbranding, mislabelling, mislabeled, unsafe, sample failure, sample failed,
  contaminated, contamination, impure, impurity, fraud, fraudulent, diluted, dilution,
  mixed with, inferior quality, unhygienic
- **action_terms**: FSSAI, food safety, food safety department, FDA, food authority,
  seized, seizure, raid, raided, arrested, arrest, fine, penalty, enforcement action,
  crackdown, inspection, tested, lab test, laboratory, complaint, license cancelled,
  notice issued, show cause, legal action, police, district administration
- **location_terms**: all major Indian states + ~25 cities (unchanged for ghee — reuse as-is)

### 5.2 Strict relevance-pipeline terms (`crawler/oil_relevance.py` — the authoritative,
later-stage logic used by `scripts/run_oil_relevance_pipeline.py`)

This is the **important one to fork for ghee** — it decides product *role* (is the
target food itself the adulterated product, vs. an adulterant in something else,
vs. non-food, vs. business/price noise):

```python
EDIBLE_OIL_TERMS = ["edible oil", "cooking oil", "mustard oil", "refined oil",
  "soybean oil", "soya oil", "palm oil", "groundnut oil", "sesame oil",
  "sunflower oil", "rice bran oil", "cottonseed oil", "vegetable oil",
  "loose oil", "loose edible oil", "coconut oil", "olive oil",
  "rapeseed-mustard oil"]

ADULTERATION_ACTION_TERMS = ["adulterated", "adulteration", "fake", "spurious",
  "contaminated", "contamination", "misbranded", "misbranding", "substandard",
  "unsafe", "rancid", "seized", "seizure", "raid", "raided", "sample failed",
  "samples failed", "failed test", "failed quality test", "failed safety test",
  "food safety", "FSSAI", "FDA", "FSDA", "Food Safety Department",
  "Food Safety Officer", "lab test", "quality test", "sample collected",
  "samples collected", "prosecution", "penalty", "fine", "banned",
  "shop sealed", "crackdown", "inspection"]   # food-safety vocabulary, reuse as-is

ADULTERANT_TERMS = ["argemone oil", "mineral oil", "castor oil", "cottonseed oil",
  "palmolein", "cheap oil"]   # things used TO adulterate oil — for ghee this
  # becomes e.g. vanaspati, vegetable oil, animal/body fat (tallow/lard),
  # starch, palm oil, margarine

NON_FOOD_OIL_TERMS = ["petrol", "diesel", "crude oil", "engine oil", "lubricant",
  "kerosene", "fuel adulteration", "oil rig", "oil rigs", "oilfield",
  "offshore oil", "ONGC", "oil refinery", "refinery", "hair oil", "essential oil",
  "massage oil", "cosmetic oil", "aromatherapy oil"]   # n/a for ghee — drop or
  # replace with ghee-irrelevant senses if any exist (none obvious)

BUSINESS_ONLY_TERMS = ["oil prices", "oil price", "edible oil prices",
  "oil imports", "oil exports", "import duty", "stock market", "commodity",
  "futures", "palm oil futures", "soybean futures", "market price", "price hike",
  "inflation"]   # adapt: "ghee prices", "ghee imports", "milk price", etc.

NON_OIL_FOOD_TERMS = ["milk", "ghee", "paneer", "dairy products", "khoya", "mawa",
  "curd", "butter", "cheese", "spice", "spices", "turmeric", "chilli", "chili",
  "masala", "tea", "honey", "sweets", "flour", "atta", "soybean corn"]
  # this is the oil pipeline's "hard-negative" list (other foods that share
  # enforcement vocabulary). For ghee this becomes the SAME kind of list but for
  # other dairy/foods: milk, paneer, khoya, mawa, curd, butter, cheese, sweets,
  # and crucially must now EXCLUDE "ghee" itself and re-include "vanaspati" as
  # a positive adulterant-of-ghee signal instead of an out-of-scope term

OUT_OF_SCOPE_FOOD_TERMS = ["ghee", "vanaspati"]
  # *** THIS IS THE LIST THAT CURRENTLY BLOCKS GHEE. For the ghee pipeline this
  # must be removed/inverted: ghee becomes the EDIBLE_OIL_TERMS-equivalent
  # (the target product), and vanaspati moves to ADULTERANT_TERMS. ***
```

There's also `ADULTERATED_PRODUCT_PATTERNS` and `ADULTERANT_ROLE_PATTERNS` —
regexes that look for `<target food> ... <adulteration word>` within a ~90-char
window (e.g. `"oil samples failed"`, `"fake ... oil"`). These need
oil→ghee word substitution but the same proximity-pattern structure works.

The Ollama LLM prompt template (`build_llm_prompt` in the same file) also
hardcodes the oil definition of relevant/irrelevant — needs a ghee-specific
rewrite (e.g. "Relevant ONLY if ghee/desi ghee/cow ghee/buffalo ghee is itself
the adulterated, fake, spurious... product. Irrelevant if ghee is merely
mentioned in a recipe, price story, or is itself used to adulterate something else").

### 5.3 The classifier's OIL_TERMS used for "oil-window" text representation
(`src/model_training/build_text_representations.py`) — a near-duplicate of
`EDIBLE_OIL_TERMS` above, deliberately **excludes** `ghee`/`vanaspati` as
positive keywords (matches the discovery NOT-block). This file builds the
`title_plus_oil_windows` representation (title + first paragraph + sentences
near an oil term ±1) used by the best-performing models. For ghee, build an
equivalent `title_plus_ghee_windows` keyed on ghee terms only (not enforcement
terms), for the same hard-negative-reduction reason.

## 6. Config files (`config/`)

| File | Purpose |
|---|---|
| `config.yaml` | Master/legacy config: date range (2021-06-01–2026-06-17), term lists, crawl/relevance/dedupe settings |
| `config_mediacloud.yaml` | Media Cloud variant + augmentation params (max_rounds, convergence_threshold, min_df, seed_keywords_file) |
| `mediacloud_seed_keywords.yaml` | ~37–56 hand-curated Round-0 seed queries for oil |
| `config_edible_oils_boolean.yaml`, `_combined.yaml`, `_round3.yaml`, `_round4.yaml` | Per-round configs used across the 4 discovery rounds actually run |
| `edible_oil_*_seed_queries.yaml` | Matching per-round query sets |
| `config_ddgs.yaml` + `queries_ddgs.yaml` | DDG no-key fallback |
| `config_gdelt10.yaml` + `queries_gdelt10.yaml` | GDELT-only, 10 queries |
| `sources.yaml` | 30+ target Indian domains, RSS feeds, blocked domains (msn.com, social/e-commerce/recipe sites) — **reusable as-is for ghee**, not oil-specific |
| `queries.yaml` | Legacy pre-built query list |

**For ghee:** clone the `config_mediacloud.yaml` + `mediacloud_seed_keywords.yaml`
pair into `config_ghee.yaml` + `ghee_seed_keywords.yaml`, point
`output_dir`/`db_path`/`run_dir` at a fresh `data/runs/ghee_<date>/` directory so
the two corpora never collide, and write new seed queries (title/boolean/proximity/
phrase families, same style as oil) around ghee adulteration vocabulary.

## 7. The 5-stage strict relevance pipeline (`scripts/run_oil_relevance_pipeline.py`)

Used after broad Media Cloud discovery to separate "X is the adulterated
product" from "X is incidental / an adulterant / non-food":

```bash
python scripts/run_oil_relevance_pipeline.py --stage metadata   # title/URL/query-only triage -> crawl_queue.csv
python scripts/run_oil_relevance_pipeline.py --stage crawl      # download + extract queued URLs
python scripts/run_oil_relevance_pipeline.py --stage rules      # apply oil_relevance.py rules to extracted text
python scripts/run_oil_relevance_pipeline.py --stage llm        # local Ollama (llama3.1:8b-instruct) reads each candidate
python scripts/run_oil_relevance_pipeline.py --stage outputs    # merge rule+LLM -> final review CSVs
```

Final outputs per run: `all_articles_review.csv`, `relevant_oil_articles.csv`,
`manual_review_articles.csv`, `irrelevant_articles.csv`, `filtering_summary.json`,
`manual_validation_sample.csv` (for human spot-check, evaluated by
`scripts/evaluate_oil_relevance_labels.py`).

This script imports directly from `crawler/oil_relevance.py` — it is the file
that needs a ghee-specific sibling (e.g. `crawler/ghee_relevance.py` with the
term lists above swapped in, then a `--stage` pipeline script pointed at it, or
parameterize `run_oil_relevance_pipeline.py` to accept a `--domain oil|ghee` flag
that selects the right term-list module).

## 8. Master corpus (`reports/master_corpus/`)

- `master_all_articles.csv` — **5,072 rows**, every discovered/reviewed URL
  across all 4 oil discovery rounds + rescreens, with full audit trail columns:
  `round_number, round_name, final_keep, final_human_label, human_review_status,
  title, source, date, url, domain, word_count, model_final_label,
  model_confidence, reason, evidence_phrase, oil_role, edible_oil_terms,
  adulteration_action_terms, negative_terms, query_family, query_id,
  article_text, llm_label, llm_confidence, llm_reason, ...`
- Of these, **486 rows have full extracted text + a confirmed human label**
  (139 relevant / 347 irrelevant as of the 2026-06-29 corpus cleanup) — this
  is the subset actually used to train classifiers.
- `master_relevant_articles.csv` / `master_irrelevant_articles.csv` — pre-filtered views
- `master_corpus_summary.json` — row counts/stats

For ghee, the natural pattern is a parallel `master_ghee_articles.csv` built the
same way (per-round discovery → relevance pipeline → human review → freeze),
not a merge into the oil file — `oil_role`/`edible_oil_terms` column semantics
are oil-specific and would need a generalized name (`food_role`,
`target_food_terms`) if you want one shared schema across both domains.

## 9. Model training pipeline (`src/model_training/`, already built for oil)

This is fully reusable infrastructure — it doesn't know about oil specifically
except through the `OIL_TERMS`-keyed window representation noted in §5.3:

| File | Purpose |
|---|---|
| `build_text_representations.py` | 3 text reps: full-article, oil-window, keyword-window |
| `final_tfidf.py` | TF-IDF (word 1-2gram + char 3-5gram) × {LogReg, LinearSVM} |
| `final_embeddings.py` | 4 sentence encoders (MiniLM, MPNet, e5-large, bge-large) × 3 pooling reps × 3 classifiers |
| `final_transformers.py` | Fine-tuned DistilBERT/RoBERTa/DeBERTa-v3 (+ optional Longformer-4096) |
| `run_final_experiments.py` | Orchestrator: TF-IDF → embeddings → transformers → weighted ensembles |
| `result_cache.py` | Resumable per-model `.pkl`/`.npz` cache — survives interrupted runs |
| `rescreen_rejected_urls.py` | Re-score previously-dropped URLs with the trained best model |

Latest oil result: best F1 = **0.836** (precision 0.868, recall 0.806) on the
cleaned 486-article corpus, via a 3-way weighted ensemble (TF-IDF LinearSVM +
bge-large RBF-SVM on oil-window + RoBERTa lead-512). Full report:
`reports/CLASSIFICATION_REPORT.md`. The same `run_final_experiments.py` should
work unmodified on a ghee corpus once a comparably-sized labelled set exists —
just point `--input` at the ghee master CSV and rename `--output-dir`.

## 10. Secrets / environment

- `.env` (gitignored, never commit) holds `MEDIACLOUD_API_KEY` (required for
  Media Cloud discovery), and optionally `GOOGLE_CSE_KEY`/`GOOGLE_CSE_CX`,
  `BING_API_KEY`, `SERPAPI_KEY`. `.env.example` is the template.
- robots.txt bypass (`respect_robots_txt=False`, `use_playwright=True`,
  `playwright_first=True`) was approved for this academic-research crawler and
  applies equally to a ghee run.

## 11. Recommended adaptation plan for ghee

1. **New term-list module**: fork `crawler/oil_relevance.py` →
   `crawler/ghee_relevance.py`. Swap `EDIBLE_OIL_TERMS` for ghee terms (ghee,
   desi ghee, cow ghee, buffalo ghee, pure ghee — verify exact phrasing against
   real article samples before finalizing), move `vanaspati` into
   `ADULTERANT_TERMS` alongside vegetable oil, animal fat/tallow, margarine,
   starch (confirm actual common adulterants from FSSAI ghee guidance, don't
   guess), drop `OUT_OF_SCOPE_FOOD_TERMS` entirely or repurpose for a different
   exclusion if needed, and rewrite the Ollama prompt's relevant/irrelevant
   definition for ghee.
2. **New discovery configs**: `config/config_ghee.yaml` +
   `config/ghee_seed_keywords.yaml`, modeled on the oil Round-0 seed file —
   same title/boolean/proximity/phrase query-family structure.
3. **New run directory**: `data/runs/ghee_<date>/` so SQLite/HTML/text never
   mix with the oil run.
4. **Run discovery → metadata → crawl → rules → llm → outputs** exactly like
   the oil pipeline (§7), pointed at the ghee config/term module.
5. **Human review** the `manual_review_articles.csv` + spot-check sample,
   same as was done for oil (the 2026-06-29 audit that flipped 12 oil articles
   found mislabeled cases mostly at the reuse/incidental boundary — expect a
   similar boundary for ghee, e.g. "ghee" mentioned in a general dairy-raid
   story vs. ghee itself being adulterated).
6. **Freeze a ghee master corpus**, then run `src/model_training/run_final_experiments.py`
   unmodified against it once there's a reasonably sized labelled set (the oil
   run needed ~486 labelled articles for stable classifier results).

## 12. Things Codex should NOT assume

- Do not reuse `OIL_TERMS`/`EDIBLE_OIL_TERMS` for ghee matching — they will
  silently exclude every ghee article (`OUT_OF_SCOPE_FOOD_TERMS` forces
  ghee-only articles to `irrelevant` today).
- Do not write into `reports/master_corpus/master_all_articles.csv` or
  `data/runs/edible_oils_*` directories — those are the frozen oil corpus.
- Common ghee adulterants (vanaspati, vegetable oil, animal fat, starch, etc.)
  are listed above as a starting hypothesis only — verify against real article
  text and/or FSSAI documentation before finalizing the term list, the same
  way the oil term lists were tuned against real false positives over several
  rounds.
