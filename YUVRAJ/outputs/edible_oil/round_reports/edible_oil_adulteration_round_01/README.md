# Edible Oil Adulteration Corpus - Round 1

This folder is the cleaned, human-reviewed output package for the first MediaCloud run.

## Scope

- Round number: 1
- Round name: `round_01_mediacloud_boolean_title_proximity`
- Date range: 2021-01-01 to 2026-06-22
- Geography: India-focused MediaCloud national and state/local collections
- Food item: edible/cooking oils only; ghee and vanaspati excluded
- Reused/used cooking oil without adulteration/fraud context is treated as irrelevant for this corpus.

## Counts

- Total reviewed articles: 285
- Relevant articles: 75
- Irrelevant articles: 210
- Unresolved articles: 0

## Key Files

- `round_01_all_articles.csv`: all human-reviewed rows, with article text.
- `round_01_relevant_articles.csv`: kept articles, with article text.
- `round_01_irrelevant_articles.csv`: dropped articles, with article text.
- `round_01_relevant_articles.jsonl`: kept articles in JSONL form.
- `round_01_review_workbook.xlsx`: formatted Excel workbook without full article text.
- `round_01_summary.json`: machine-readable summary and provenance.
