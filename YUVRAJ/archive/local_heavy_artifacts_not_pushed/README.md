# Local Heavy Artifacts Not Included

This archive note records large artifacts that were deliberately left outside the curated `YUVRAJ` handoff folder.

## Excluded From GitHub Handoff

- `news_crawler/data/runs/*/raw_html/`
- `news_crawler/data/runs/*/cleaned_text/`
- `news_crawler/reports/model_training*/trained_models/`
- `news_crawler/reports/model_training*/_run_state/`

Reason:

- Raw crawl folders are useful for local forensic checks but are too noisy for GitHub.
- Transformer checkpoints are hundreds of MB each and should not be pushed in normal Git history.
- Reproducible scripts, configs, review workbooks, summary CSV/JSON files, and corpus outputs are included in `YUVRAJ`.

Important local source locations in the working repo:

- Ghee raw run: `news_crawler/data/runs/ghee_adulteration_round_01_2026-06-30/`
- Edible-oil master corpus: `news_crawler/reports/master_corpus/`
- Edible-oil classifier outputs: `news_crawler/reports/model_training_cleaned/`
