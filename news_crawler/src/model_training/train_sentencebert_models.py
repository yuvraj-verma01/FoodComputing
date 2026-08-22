"""Sentence-BERT embedding classifiers.

Model 4 — sbert_lr : all-MiniLM-L6-v2 embeddings + Logistic Regression

Embeddings are pre-computed once per representation (frozen encoder), then
stratified CV is run on the embedding matrix + LR. This is both efficient
and correct: the encoder is never tuned on the training fold labels.
"""

from __future__ import annotations

import json
import joblib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .evaluate_models import cross_validate_model

DEFAULT_SBERT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ── Embedding helpers ─────────────────────────────────────────────────────────

def load_sbert(model_name: str = DEFAULT_SBERT_MODEL):
    """Lazy-import and load a SentenceTransformer model."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError(
            "sentence-transformers is required for SBERT models. "
            "Install with: pip install sentence-transformers"
        )
    print(f"  Loading SBERT model: {model_name}")
    return SentenceTransformer(model_name)


def encode_texts(
    texts: list[str],
    model,
    batch_size: int = 32,
    show_progress: bool = True,
) -> np.ndarray:
    """Encode a list of texts into a (N, D) embedding matrix."""
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
        normalize_embeddings=True,  # unit vectors; cosine ~ dot product
    )
    return embeddings.astype(np.float32)


def _make_lr() -> LogisticRegression:
    return LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        C=1.0,
        solver="lbfgs",
        random_state=42,
    )


# ── Training ──────────────────────────────────────────────────────────────────

def train_and_evaluate_sbert(
    representations: dict[str, list[str]],
    labels: np.ndarray,
    df_meta: pd.DataFrame,
    output_dir: Path,
    sbert_model_name: str = DEFAULT_SBERT_MODEL,
    n_splits: int = 5,
) -> list[dict]:
    """Run stratified CV for SBERT+LR across all representations.

    Embeddings are computed once per representation then reused across folds.
    Returns a list of CV result dicts.
    """
    models_dir = output_dir / "trained_models"
    models_dir.mkdir(parents=True, exist_ok=True)

    sbert = load_sbert(sbert_model_name)
    cv_results: list[dict] = []

    for repr_name, texts in representations.items():
        model_name = "sbert_lr"
        print(f"  Encoding [{repr_name}] with SBERT ...", flush=True)
        embeddings = encode_texts(texts, sbert, show_progress=True)

        # Scale embeddings (unit-normalised inputs benefit from StandardScaler
        # for the LR weight initialisation, though the effect is small here)
        scaler = StandardScaler()
        embeddings_scaled = scaler.fit_transform(embeddings)

        print(f"  CV: {model_name} × {repr_name} ...", end=" ", flush=True)
        lr = _make_lr()
        result = cross_validate_model(
            estimator=lr,
            X=embeddings_scaled,
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

        # Refit on full dataset and save artifacts
        full_lr = _make_lr()
        full_lr.fit(embeddings_scaled, labels)

        artifact_stem = f"{model_name}_{repr_name}"
        joblib.dump(full_lr,    models_dir / f"{artifact_stem}_classifier.joblib")
        joblib.dump(scaler,     models_dir / f"{artifact_stem}_scaler.joblib")

        # Config so the rescreen script knows how to reconstruct this model
        cfg = {
            "model_type":    "sbert_lr",
            "sbert_model":   sbert_model_name,
            "representation": repr_name,
            "classifier_path": str(models_dir / f"{artifact_stem}_classifier.joblib"),
            "scaler_path":     str(models_dir / f"{artifact_stem}_scaler.joblib"),
        }
        config_path = models_dir / f"{artifact_stem}_config.json"
        config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    return cv_results
