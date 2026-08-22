"""Stratified cross-validation, metrics computation, and threshold tuning."""

from __future__ import annotations

from typing import Any, Optional, Union

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold


# ── Metric helpers ────────────────────────────────────────────────────────────

def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
) -> dict[str, float]:
    """Compute all classification metrics for the positive (relevant) class."""
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    metrics: dict[str, float] = {
        "accuracy":  float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "recall":    float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "f1":        float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
        "roc_auc": float("nan"),
        "pr_auc":  float("nan"),
    }

    if y_proba is not None and len(np.unique(y_true)) > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba))
        metrics["pr_auc"]  = float(average_precision_score(y_true, y_proba))

    return metrics


# ── Threshold tuning ──────────────────────────────────────────────────────────

def tune_thresholds(y_true: np.ndarray, y_proba: np.ndarray) -> dict:
    """Find three operating points: high_recall, balanced (best F1), high_precision."""
    y_true = np.asarray(y_true, dtype=int)
    thresholds = np.arange(0.05, 0.96, 0.01)

    best_f1     = {"threshold": 0.5, "f1": -1.0, "precision": 0.0, "recall": 0.0}
    best_recall = {"threshold": 0.3, "f1":  0.0, "precision": 0.0, "recall": -1.0}
    best_prec   = {"threshold": 0.7, "f1":  0.0, "precision": -1.0, "recall": 0.0}

    for t in thresholds:
        preds = (y_proba >= t).astype(int)
        p = float(precision_score(y_true, preds, pos_label=1, zero_division=0))
        r = float(recall_score(y_true, preds, pos_label=1, zero_division=0))
        f = float(f1_score(y_true, preds, pos_label=1, zero_division=0))

        if f > best_f1["f1"]:
            best_f1 = {"threshold": float(t), "f1": f, "precision": p, "recall": r}

        # high_recall: maximise recall, require at least 25% precision to avoid predicting all-positive
        if r > best_recall["recall"] and p >= 0.25:
            best_recall = {"threshold": float(t), "f1": f, "precision": p, "recall": r}

        # high_precision: maximise precision, require at least 40% recall to stay useful
        if p > best_prec["precision"] and r >= 0.40:
            best_prec = {"threshold": float(t), "f1": f, "precision": p, "recall": r}

    return {
        "high_recall":     round(best_recall["threshold"], 2),
        "balanced":        round(best_f1["threshold"], 2),
        "high_precision":  round(best_prec["threshold"], 2),
        "details": {
            "high_recall":    best_recall,
            "balanced":       best_f1,
            "high_precision": best_prec,
        },
    }


# ── Cross-validation ──────────────────────────────────────────────────────────

def cross_validate_model(
    estimator: Any,
    X: Union[list[str], np.ndarray],
    y: np.ndarray,
    df_meta: pd.DataFrame,
    model_name: str,
    repr_name: str,
    n_splits: int = 5,
    random_state: int = 42,
) -> dict:
    """Stratified k-fold CV.  Works for both sklearn Pipelines and plain estimators.

    X can be a list[str] (for TF-IDF pipelines) or np.ndarray (for embedding models).
    """
    y = np.asarray(y, dtype=int)
    is_array = isinstance(X, np.ndarray)

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)

    all_indices: list[int] = []
    all_true:   list[int] = []
    all_pred:   list[int] = []
    all_proba:  list[float] = []
    has_proba = hasattr(estimator, "predict_proba")

    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X if is_array else list(range(len(X))), y)):
        X_train = X[train_idx] if is_array else [X[i] for i in train_idx]
        X_test  = X[test_idx]  if is_array else [X[i] for i in test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        estimator.fit(X_train, y_train)
        y_pred = estimator.predict(X_test)

        if has_proba:
            proba = estimator.predict_proba(X_test)[:, 1]
            all_proba.extend(proba.tolist())

        all_indices.extend(test_idx.tolist())
        all_true.extend(y_test.tolist())
        all_pred.extend(y_pred.tolist())

    # Re-order all lists to original row order
    order = np.argsort(all_indices)
    all_true_arr  = np.array(all_true)[order]
    all_pred_arr  = np.array(all_pred)[order]
    all_proba_arr = np.array(all_proba)[order] if all_proba else None

    metrics = compute_metrics(all_true_arr, all_pred_arr, all_proba_arr)

    # Build per-sample predictions DataFrame
    records = []
    for orig_idx, true, pred in zip(
        np.array(all_indices)[order], all_true_arr, all_pred_arr
    ):
        row = df_meta.iloc[orig_idx]
        rec = {
            "article_id":   row.get("article_id", f"row_{orig_idx}"),
            "title":        row.get("title", ""),
            "url":          row.get("url", ""),
            "true_label":   int(true),
            "predicted_label": int(pred),
            "predicted_probability": float("nan"),
            "model_name":   model_name,
            "representation": repr_name,
        }
        records.append(rec)

    pred_df = pd.DataFrame(records)
    if all_proba_arr is not None:
        pred_df["predicted_probability"] = all_proba_arr

    # Threshold tuning on the full CV probabilities
    thresholds = None
    if all_proba_arr is not None:
        thresholds = tune_thresholds(all_true_arr, all_proba_arr)

    return {
        "model_name":   model_name,
        "representation": repr_name,
        "metrics":      metrics,
        "thresholds":   thresholds,
        "predictions_df": pred_df,
        "all_true":     all_true_arr,
        "all_pred":     all_pred_arr,
        "all_proba":    all_proba_arr,
    }


# ── Summary helpers ───────────────────────────────────────────────────────────

def results_to_comparison_df(results: list[dict]) -> pd.DataFrame:
    """Convert a list of CV result dicts into a summary DataFrame."""
    rows = []
    for r in results:
        m = r["metrics"]
        rows.append({
            "model_name":    r["model_name"],
            "representation": r["representation"],
            "accuracy":      round(m["accuracy"], 4),
            "precision":     round(m["precision"], 4),
            "recall":        round(m["recall"], 4),
            "f1":            round(m["f1"], 4),
            "roc_auc":       round(m["roc_auc"], 4) if not np.isnan(m["roc_auc"]) else None,
            "pr_auc":        round(m["pr_auc"], 4)  if not np.isnan(m["pr_auc"])  else None,
            "tp": m["tp"], "fp": m["fp"], "fn": m["fn"], "tn": m["tn"],
        })
    return pd.DataFrame(rows).sort_values("f1", ascending=False).reset_index(drop=True)


def select_best_models(results: list[dict]) -> tuple[dict, dict]:
    """Return (best_by_f1, best_by_recall) from a list of CV results."""
    best_f1     = max(results, key=lambda r: r["metrics"]["f1"])
    best_recall = max(results, key=lambda r: r["metrics"]["recall"])
    return best_f1, best_recall


def extract_false_cases(cv_result: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (false_positives_df, false_negatives_df) from a CV result."""
    df = cv_result["predictions_df"].copy()
    fp = df[(df["true_label"] == 0) & (df["predicted_label"] == 1)].copy()
    fn = df[(df["true_label"] == 1) & (df["predicted_label"] == 0)].copy()
    return fp, fn
