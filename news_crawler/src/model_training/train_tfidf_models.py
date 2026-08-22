"""TF-IDF based classifiers.

Model 1 — tfidf_word_lr    : unigrams + Logistic Regression
Model 2 — tfidf_phrase_lr  : 1-3grams + Logistic Regression
Model 3 — tfidf_phrase_svm : 1-3grams + LinearSVC (calibrated)
"""

from __future__ import annotations

import joblib
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from .evaluate_models import cross_validate_model


# ── Pipeline factories ────────────────────────────────────────────────────────

def _tfidf_word_lr() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 1),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,
            strip_accents="unicode",
            token_pattern=r"(?u)\b\w\w+\b",
        )),
        ("clf", LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            C=1.0,
            solver="lbfgs",
            random_state=42,
        )),
    ])


def _tfidf_phrase_lr() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 3),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,
            strip_accents="unicode",
            token_pattern=r"(?u)\b\w\w+\b",
        )),
        ("clf", LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            C=1.0,
            solver="lbfgs",
            random_state=42,
        )),
    ])


def _tfidf_phrase_svm() -> Pipeline:
    svm = LinearSVC(class_weight="balanced", max_iter=2000, C=1.0, random_state=42)
    calibrated = CalibratedClassifierCV(svm, cv=3, method="sigmoid")
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 3),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,
            strip_accents="unicode",
            token_pattern=r"(?u)\b\w\w+\b",
        )),
        ("clf", calibrated),
    ])


PIPELINE_FACTORIES = {
    "tfidf_word_lr":    _tfidf_word_lr,
    "tfidf_phrase_lr":  _tfidf_phrase_lr,
    "tfidf_phrase_svm": _tfidf_phrase_svm,
}


# ── Feature importance ────────────────────────────────────────────────────────

def extract_feature_importance(
    pipeline: Pipeline,
    model_name: str,
    repr_name: str,
    n_top: int = 30,
) -> list[dict]:
    """Extract top positive and negative TF-IDF features from a fitted pipeline."""
    vectorizer = pipeline.named_steps["tfidf"]
    clf        = pipeline.named_steps["clf"]
    feature_names = vectorizer.get_feature_names_out()

    # Handle CalibratedClassifierCV wrapping LinearSVC
    if hasattr(clf, "coef_"):
        coef = clf.coef_[0]
    elif hasattr(clf, "calibrated_classifiers_"):
        coef = np.mean(
            [c.estimator.coef_[0] for c in clf.calibrated_classifiers_], axis=0
        )
    else:
        return []

    top_pos = coef.argsort()[-n_top:][::-1]
    top_neg = coef.argsort()[:n_top]

    records = []
    for idx in top_pos:
        records.append({
            "feature": feature_names[idx],
            "coefficient": round(float(coef[idx]), 5),
            "direction": "positive",
            "model_name": model_name,
            "representation": repr_name,
        })
    for idx in top_neg:
        records.append({
            "feature": feature_names[idx],
            "coefficient": round(float(coef[idx]), 5),
            "direction": "negative",
            "model_name": model_name,
            "representation": repr_name,
        })
    return records


# ── Training ──────────────────────────────────────────────────────────────────

def train_and_evaluate_tfidf(
    representations: dict[str, list[str]],
    labels: np.ndarray,
    df_meta: pd.DataFrame,
    output_dir: Path,
    n_splits: int = 5,
) -> tuple[list[dict], list[dict]]:
    """Run stratified CV for all TF-IDF models × all representations.

    Returns
    -------
    cv_results : list of CV result dicts (one per model × representation)
    feature_records : list of feature importance dicts (for tabular export)
    """
    models_dir = output_dir / "trained_models"
    models_dir.mkdir(parents=True, exist_ok=True)

    cv_results: list[dict] = []
    feature_records: list[dict] = []

    for model_name, factory in PIPELINE_FACTORIES.items():
        for repr_name, texts in representations.items():
            print(f"  CV: {model_name} × {repr_name} ...", end=" ", flush=True)
            pipeline = factory()
            result = cross_validate_model(
                estimator=pipeline,
                X=texts,
                y=labels,
                df_meta=df_meta,
                model_name=model_name,
                repr_name=repr_name,
                n_splits=n_splits,
            )
            m = result["metrics"]
            print(
                f"F1={m['f1']:.3f}  Prec={m['precision']:.3f}  "
                f"Rec={m['recall']:.3f}  ROC-AUC={m.get('roc_auc', float('nan')):.3f}"
            )
            cv_results.append(result)

            # Refit on full dataset and save
            full_pipeline = factory()
            full_pipeline.fit(texts, labels)
            model_path = models_dir / f"{model_name}_{repr_name}.joblib"
            joblib.dump(full_pipeline, model_path)

            # Feature importance from the full-dataset fit
            feats = extract_feature_importance(full_pipeline, model_name, repr_name)
            feature_records.extend(feats)

    return cv_results, feature_records
