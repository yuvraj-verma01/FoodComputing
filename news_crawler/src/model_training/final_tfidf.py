"""Final-run sparse TF-IDF models.

Vectoriser = word (1–2) ⊕ char_wb (3–5) n-grams, union'd.
Two classifiers × three representations = 6 models:
  - tfidf_logreg     (LogisticRegression, class_weight=balanced)
  - tfidf_linsvm     (LinearSVC, calibrated for probabilities)
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from . import result_cache as rc
from .evaluate_models import cross_validate_model


def _vectoriser() -> FeatureUnion:
    return FeatureUnion([
        ("word", TfidfVectorizer(
            analyzer="word", ngram_range=(1, 2), min_df=2, max_df=0.95,
            sublinear_tf=True, strip_accents="unicode",
            token_pattern=r"(?u)\b\w\w+\b")),
        ("char", TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_df=0.95,
            sublinear_tf=True, strip_accents="unicode")),
    ])


def _logreg() -> Pipeline:
    return Pipeline([
        ("features", _vectoriser()),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=2000,
                                   C=1.0, solver="lbfgs", random_state=42)),
    ])


def _linsvm() -> Pipeline:
    svm = LinearSVC(class_weight="balanced", max_iter=5000, C=1.0, random_state=42)
    return Pipeline([
        ("features", _vectoriser()),
        ("clf", CalibratedClassifierCV(svm, cv=3, method="sigmoid")),
    ])


FACTORIES = {"tfidf_logreg": _logreg, "tfidf_linsvm": _linsvm}


def train_and_evaluate_final_tfidf(
    representations: dict[str, list[str]],
    labels: np.ndarray,
    df_meta: pd.DataFrame,
    output_dir: Path,
    n_splits: int = 5,
) -> list[dict]:
    ckpt_dir = Path(output_dir) / "trained_models" / "final_checkpoints" / "tfidf"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for model_name, factory in FACTORIES.items():
        for repr_name, texts in representations.items():
            cached = rc.load_result(output_dir, model_name, repr_name)
            if cached is not None:
                print(f"  [cached] {model_name} × {repr_name}  F1={cached['metrics']['f1']:.3f}")
                results.append(cached)
                continue

            print(f"  CV: {model_name} × {repr_name} ...", end=" ", flush=True)
            result = cross_validate_model(
                estimator=factory(), X=texts, y=labels, df_meta=df_meta,
                model_name=model_name, repr_name=repr_name, n_splits=n_splits)
            m = result["metrics"]
            print(f"F1={m['f1']:.3f}  P={m['precision']:.3f}  "
                  f"R={m['recall']:.3f}  ROC-AUC={m.get('roc_auc', float('nan')):.3f}")

            # Deployable checkpoint: refit on the full dataset.
            full = factory(); full.fit(texts, labels)
            joblib.dump(full, ckpt_dir / f"{model_name}__{repr_name}.joblib")

            rc.save_result(output_dir, result)
            results.append(result)
    return results
