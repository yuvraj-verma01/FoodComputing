# Milk relevance classifier

The selected Milk relevance model is a calibrated LinearSVC over full-title and
full-body TF-IDF word unigrams and bigrams. The evaluation workbook contains
1,384 labeled articles and five-fold out-of-fold results:

| Metric | Score |
| --- | ---: |
| F1 | 0.8323 |
| Precision | 0.8424 |
| Recall | 0.8225 |
| ROC-AUC | 0.9635 |
| PR-AUC | 0.9118 |

`score_incident_articles.py` fits a separate deployment model on all 1,384
labeled records and scores every published Milk incident. It updates the
combined incident JSON, article-level CSV, and current-data report together.
Evaluation metrics remain out-of-fold and must not be recalculated from the
deployment predictions.

Install the pinned runtime in an isolated environment, then run from the
repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r milk_classifier/requirements.txt
.venv/bin/python milk_classifier/score_incident_articles.py \
  --workbook milk_classifier/results/milk_model_training/Milk_Adulteration_Model_Results.xlsx \
  --data-dir food-safety-observatory-with-changes/public/data \
  --model-output milk_classifier/results/milk_model_training/milk_relevance_tfidf_calibrated_linsvc_fulltext_v1.joblib \
  --audit-output milk_classifier/results/milk_model_training/milk_relevance_tfidf_calibrated_linsvc_fulltext_v1.audit.json
```

The 2026-08-22 release scored all 196 published Milk records: 126 relevant and
70 irrelevant at the 0.5 threshold. The fitted checkpoint and run audit are
stored beside the evaluation workbook.
