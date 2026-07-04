# Food Adulteration News Corpus - Yuvraj Handoff

This folder is the cleaned project handoff for the edible-oil and ghee news-crawling work. It is organized so the current outputs, review files, configs, and scripts are easy to find without digging through raw crawls, temporary checkpoints, or older intermediate clutter.

## Current Status

### Edible oil

The edible-oil workflow is complete through multiple discovery/review/modeling rounds.

What was done:

1. Seed articles were used to extract initial edible-oil/adulteration keywords.
2. MediaCloud Boolean, phrase, title-only, and proximity queries were built for Indian collections.
3. Discovered URLs were filtered by metadata/title rules.
4. Candidate articles were crawled and scored using rules plus local LLM classification.
5. Human review labels were applied.
6. A master edible-oil corpus was created with relevant/irrelevant labels and round numbers.
7. A supervised edible-oil relevance classifier was trained and evaluated.

Key edible-oil outputs:

- `outputs/edible_oil/master_corpus/master_all_articles.csv`
- `outputs/edible_oil/master_corpus/master_corpus.xlsx`
- `outputs/edible_oil/master_corpus/master_relevant_articles.csv`
- `outputs/edible_oil/master_corpus/master_irrelevant_articles.csv`
- `outputs/edible_oil/classifier_report/CLASSIFICATION_REPORT.md`
- `outputs/edible_oil/model_training_summaries/best_model_summary.json`
- `outputs/edible_oil/model_training_summaries/model_comparison.csv`

Classifier result summary:

- Cleaned corpus: 486 labeled edible-oil articles.
- Relevant: 139.
- Irrelevant: 347.
- Best cleaned-corpus model reported F1 = 0.836, precision = 0.868, recall = 0.806.
- The best reported model was an ensemble using TF-IDF, bge-large embeddings, and RoBERTa.

### Ghee

The ghee workflow has completed Round 1 discovery, crawl, and local LLM scoring. Human review is the next step.

What was done:

1. `Ghee sample articles.docx` was used as the ghee seed document.
2. Keywords were extracted from the seed articles.
3. A review workbook was made and manually approved keywords were used.
4. Round 1 MediaCloud queries were generated using only approved ghee terms.
5. Queries used the same broad strategy as edible oil: phrase, Boolean, title-only, and proximity queries.
6. URL discovery was run against Indian MediaCloud collections.
7. Candidate URLs were filtered through metadata/title rules.
8. Candidate articles were crawled and full text was extracted where possible.
9. Local LLM classification was run on all successfully or partially extracted candidate articles.
10. A review workbook was created for human labeling.

Ghee Round 1 counts:

- Discovered URLs: 2614.
- Metadata/title candidate URLs: 1138.
- LLM-scored full-text articles: 1055.
- LLM labeled relevant: 851.
- LLM labeled irrelevant: 204.
- Current human `keep` labels: blank for all 1055 rows.

Most important ghee file:

- `outputs/ghee/round_01_fulltext_llm_review/ghee_relevance_fulltext/ghee_fulltext_llm_review.xlsx`

Open that workbook and fill the `keep` column:

- `1` means keep/relevant.
- `0` means drop/irrelevant.

Everything not marked `1` should be treated as `0` only after review is complete and that rule is intentionally applied.

## Folder Map

### `source_documents/`

Seed/source documents used for the project.

- `Ghee sample articles.docx`
- `oil_sample_articles.docx`

### `code/`

Runnable code copied from the working repo.

- `code/crawler/` - crawler package, storage, discovery, extraction, rule relevance.
- `code/scripts/` - project scripts for query building, discovery, crawling, review workbook generation, keyword extraction, corpus merging, and model reports.
- `code/model_training/` - supervised edible-oil model training/evaluation code.
- `code/requirements.txt` - Python dependencies from the working repo.
- `code/README.md` - original crawler README.

### `configs/`

Relevant YAML config/query files.

Important ghee files:

- `config_ghee_round1.yaml`
- `ghee_round1_seed_queries.yaml`

Important edible-oil files:

- `config_edible_oils_boolean.yaml`
- `config_edible_oils_round3.yaml`
- `config_edible_oils_round4.yaml`
- `edible_oil_boolean_seed_queries.yaml`
- `edible_oil_round3_seed_queries.yaml`
- `edible_oil_round4_seed_queries.yaml`

### `outputs/ghee/`

Current ghee outputs.

- `round_01_keyword_seed/` - seed keyword extraction and review files.
- `round_01_discovery/` - MediaCloud query/discovery outputs and URL review workbook.
- `round_01_fulltext_llm_review/` - crawl log, LLM results, scored CSV, summary JSON, and the main review workbook.

Main file to review next:

- `outputs/ghee/round_01_fulltext_llm_review/ghee_relevance_fulltext/ghee_fulltext_llm_review.xlsx`

### `outputs/edible_oil/`

Final edible-oil corpus, classifier report, summaries, and round reports.

### `archive/`

Archive/indexes for old or intermediate work. Heavy local artifacts are intentionally not copied into this handoff folder.

## What Was Not Copied

The following were intentionally excluded from `YUVRAJ` because they are large, noisy, or not appropriate for GitHub:

- Raw HTML crawls.
- Cleaned text dumps for every crawled article.
- Transformer checkpoints and large model binaries.
- Temporary `_run_state` caches.
- Old duplicate model backup folders with trained binaries.

The important review workbooks, CSV/JSON summaries, scripts, and configs are included.

## Immediate Next Steps

1. Open `outputs/ghee/round_01_fulltext_llm_review/ghee_relevance_fulltext/ghee_fulltext_llm_review.xlsx`.
2. Fill the `keep` column with `1` for relevant ghee adulteration articles and `0` for irrelevant articles.
3. After human review, merge ghee labels into a ghee master corpus.
4. Compare the edible-oil-trained classifier on the human-labeled ghee corpus.
5. Extract Round 2 ghee keywords only from newly human-approved relevant ghee articles.
6. Build Round 2 ghee queries from approved keywords only, keeping the same process: phrase, Boolean, title-only, and proximity queries.

## Method Notes

- Ghee query terms were restricted to approved terms only after the earlier issue where extra junk terms were added without approval.
- Ghee was not deduplicated against the edible-oil corpus.
- The ghee full-text LLM review uses the crawled article text, not metadata alone.
- The edible-oil classifier should be evaluated on ghee as an out-of-domain transfer test, not assumed to be a final ghee classifier.
