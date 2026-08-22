"""Smoke test for src/model_training imports and core logic."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

# ── Imports ───────────────────────────────────────────────────────────────────
print("Testing imports...")
from src.model_training.utils import (
    load_and_validate, save_csv, save_json, classification_label
)
print("  utils                        OK")

from src.model_training.build_text_representations import (
    build_representations, build_single, split_sentences,
    REPR_NAMES, _keyword_pattern,
)
print("  build_text_representations   OK")

from src.model_training.evaluate_models import (
    compute_metrics, cross_validate_model, tune_thresholds,
    results_to_comparison_df, select_best_models, extract_false_cases,
)
print("  evaluate_models              OK")

from src.model_training.train_tfidf_models import (
    train_and_evaluate_tfidf, PIPELINE_FACTORIES, extract_feature_importance,
)
print("  train_tfidf_models           OK")

# ── Representation smoke test ─────────────────────────────────────────────────
print("\nBuilding representations on 2-row DataFrame ...")
df_tiny = pd.DataFrame({
    "title":        ["Fake mustard oil seized in Mumbai raid",
                     "Oil prices rise in India"],
    "article_text": [
        "FSSAI officials raided a unit producing spurious edible oil. "
        "500 kg of adulterated mustard oil was seized. The oil failed safety tests.",
        "Edible oil prices rose by 3 percent this week due to imports.",
    ],
    "label":       [1, 0],
    "article_id":  ["a1", "a2"],
    "url":         ["http://example.com/1", "http://example.com/2"],
})
reprs = build_representations(df_tiny)
for name, texts in reprs.items():
    assert len(texts) == 2, f"Expected 2 texts for {name}"
    assert texts[0],        f"Empty text for repr={name}, row=0"
print("  All 4 representations built OK")

# Keyword window should include the oil/adulteration sentences
kw = reprs["title_plus_keyword_windows"][0]
assert "mustard oil" in kw.lower(), "keyword window missing 'mustard oil'"
assert "seized"      in kw.lower(), "keyword window missing 'seized'"
print("  Keyword window content       OK")

# ── CV smoke test ─────────────────────────────────────────────────────────────
print("\nRunning CV smoke test (60 rows, 3-fold) ...")
n = 60
titles2 = ["edible oil seized FSSAI raid"] * 30 + ["oil commodity prices market"] * 30
bodies2 = [
    "Adulterated mustard oil raided by FSSAI. Samples failed test."
] * 30 + [
    "Commodity oil prices rose sharply due to import duties."
] * 30
df_syn = pd.DataFrame({
    "title":       titles2,
    "article_text": bodies2,
    "label":       [1] * 30 + [0] * 30,
    "article_id":  [str(i) for i in range(n)],
    "url":         [""] * n,
})
reprs2 = build_representations(df_syn)
labels2 = df_syn["label"].values

pipeline = PIPELINE_FACTORIES["tfidf_word_lr"]()
result = cross_validate_model(
    pipeline, reprs2["title_only"], labels2, df_syn,
    "tfidf_word_lr", "title_only", n_splits=3,
)
m = result["metrics"]
print(f"  tfidf_word_lr × title_only: F1={m['f1']:.3f}  Rec={m['recall']:.3f}")
assert m["f1"] > 0.5, f"Expected F1 > 0.5 on synthetic data, got {m['f1']:.3f}"

# ── Threshold tuning ──────────────────────────────────────────────────────────
if result["all_proba"] is not None:
    t = tune_thresholds(result["all_true"], result["all_proba"])
    print(f"  Thresholds: high_recall={t['high_recall']}  "
          f"balanced={t['balanced']}  high_precision={t['high_precision']}")

# ── False case extraction ─────────────────────────────────────────────────────
fp, fn = extract_false_cases(result)
print(f"  False positives: {len(fp)}  False negatives: {len(fn)}")

# ── classification_label helper ───────────────────────────────────────────────
assert classification_label(0.80, 0.35, 0.65) == "candidate_relevant"
assert classification_label(0.50, 0.35, 0.65) == "manual_review"
assert classification_label(0.20, 0.35, 0.65) == "candidate_irrelevant"
print("  classification_label         OK")

# ── SBERT availability check (non-fatal) ─────────────────────────────────────
print("\nChecking optional dependencies ...")
try:
    from sentence_transformers import SentenceTransformer  # noqa
    print("  sentence-transformers        INSTALLED")
except ImportError:
    print("  sentence-transformers        NOT INSTALLED  "
          "(install: pip install sentence-transformers)")

try:
    import torch        # noqa
    import transformers # noqa
    print("  torch + transformers         INSTALLED (HF fine-tuning available)")
except ImportError:
    print("  torch / transformers         NOT INSTALLED  "
          "(install: pip install torch transformers  for --include-hf)")

print("\nAll smoke tests passed.")
