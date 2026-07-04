"""Apply the best trained classifier to previously-rejected articles.

Usage
-----
python -m src.model_training.rescreen_rejected_urls \\
    --input  reports/rejected_urls/rejected_with_body_text.csv \\
    --model  reports/model_training/trained_models/best_model.joblib \\
    --config reports/model_training/trained_models/best_model_config.json \\
    --output-dir reports/model_training

Input CSV must contain:  title, article_text  (url is optional but helpful)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.model_training.build_text_representations import build_single
from src.model_training.utils import save_csv, save_json


# ── Default thresholds (overridable via CLI) ──────────────────────────────────
DEFAULT_HIGH_RECALL_T    = 0.35
DEFAULT_HIGH_PRECISION_T = 0.65


def _load_input(input_path: str) -> pd.DataFrame:
    p = Path(input_path)
    if not p.exists():
        sys.exit(f"ERROR: Input file not found: {input_path}")
    df = pd.read_csv(p, low_memory=False)
    print(f"Loaded {len(df):,} rows from {p.name}")

    # Normalise column names
    df.columns = [c.strip() for c in df.columns]

    missing = {"title", "article_text"} - set(df.columns)
    if missing:
        sys.exit(
            f"ERROR: Missing columns: {missing}. "
            f"Available: {sorted(df.columns.tolist())}"
        )

    df["title"]        = df["title"].fillna("").astype(str).str.strip()
    df["article_text"] = df["article_text"].fillna("").astype(str).str.strip()

    n_before = len(df)
    df = df[df["article_text"] != ""].copy()
    dropped = n_before - len(df)
    if dropped:
        print(f"Dropped {dropped:,} rows with empty article_text.")

    if "url" not in df.columns:
        df["url"] = ""

    return df.reset_index(drop=True)


def _build_texts(df: pd.DataFrame, repr_name: str) -> list[str]:
    return [
        build_single(row["title"], row["article_text"], repr_name)
        for _, row in df.iterrows()
    ]


def _predict_tfidf_pipeline(
    pipeline, texts: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    preds = pipeline.predict(texts)
    probas = (
        pipeline.predict_proba(texts)[:, 1]
        if hasattr(pipeline, "predict_proba")
        else np.where(preds == 1, 0.8, 0.2)
    )
    return np.asarray(preds, dtype=int), np.asarray(probas, dtype=float)


def _predict_sbert(
    config: dict,
    texts: list[str],
    model_dir: Path,
) -> tuple[np.ndarray, np.ndarray]:
    from sentence_transformers import SentenceTransformer

    sbert = SentenceTransformer(config["sbert_model"])
    embeddings = sbert.encode(
        texts, batch_size=32, show_progress_bar=True,
        convert_to_numpy=True, normalize_embeddings=True,
    ).astype(np.float32)

    scaler_path = Path(config["scaler_path"])
    if not scaler_path.is_absolute():
        scaler_path = model_dir / scaler_path.name
    scaler = joblib.load(scaler_path)
    embeddings = scaler.transform(embeddings)

    clf_path = Path(config["classifier_path"])
    if not clf_path.is_absolute():
        clf_path = model_dir / clf_path.name
    clf = joblib.load(clf_path)

    preds  = clf.predict(embeddings)
    probas = clf.predict_proba(embeddings)[:, 1]
    return np.asarray(preds, dtype=int), np.asarray(probas, dtype=float)


def rescreen(
    input_path: str,
    model_path: str,
    config_path: Optional[str] = None,
    output_dir: str = "reports/model_training",
    high_recall_t: float    = DEFAULT_HIGH_RECALL_T,
    high_precision_t: float = DEFAULT_HIGH_PRECISION_T,
    audit_sample_n: int     = 20,
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    df = _load_input(input_path)

    # Load model config
    if config_path:
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    else:
        # Try co-located <model_path>_config.json
        cfg_guess = Path(model_path).with_suffix("").with_suffix("") \
            .parent / (Path(model_path).stem + "_config.json")
        if cfg_guess.exists():
            config = json.loads(cfg_guess.read_text(encoding="utf-8"))
        else:
            # Assume tfidf_pipeline with title_plus_keyword_windows
            config = {
                "model_type":    "tfidf_pipeline",
                "representation": "title_plus_keyword_windows",
            }
            print("WARNING: No config found, assuming tfidf_pipeline + "
                  "title_plus_keyword_windows")

    repr_name  = config.get("representation", "title_plus_keyword_windows")
    model_type = config.get("model_type", "tfidf_pipeline")
    model_dir  = Path(model_path).parent

    print(f"Building text representation: {repr_name}")
    texts = _build_texts(df, repr_name)

    print(f"Predicting with model_type={model_type} ...")
    if model_type == "tfidf_pipeline":
        pipeline = joblib.load(model_path)
        preds, probas = _predict_tfidf_pipeline(pipeline, texts)
    elif model_type == "sbert_lr":
        preds, probas = _predict_sbert(config, texts, model_dir)
    else:
        sys.exit(f"ERROR: Unsupported model_type={model_type!r}. "
                 f"Only 'tfidf_pipeline' and 'sbert_lr' are supported for rescreening.")

    # Assign review buckets
    buckets = np.where(
        probas >= high_precision_t, "candidate_relevant",
        np.where(probas >= high_recall_t, "manual_review", "candidate_irrelevant")
    )

    df["predicted_probability"] = probas.round(4)
    df["predicted_label"]       = preds
    df["review_bucket"]         = buckets

    # Sort by probability descending
    df = df.sort_values("predicted_probability", ascending=False).reset_index(drop=True)

    # ── Output 1: full ranked table ───────────────────────────────────────────
    out_cols = [c for c in
                ["title", "url", "predicted_probability", "predicted_label",
                 "review_bucket", "article_text", "date", "source"]
                if c in df.columns]
    save_csv(df[out_cols], out / "rejected_rescreen_ranked.csv",
             "all rescreened articles ranked by probability")

    # ── Output 2: high-confidence relevant ───────────────────────────────────
    high_rel = df[df["review_bucket"] == "candidate_relevant"].copy()
    save_csv(high_rel[out_cols], out / "high_confidence_relevant_for_review.csv",
             f"high-confidence relevant (p>={high_precision_t})")

    # ── Output 3: uncertain / manual review ──────────────────────────────────
    uncertain = df[df["review_bucket"] == "manual_review"].copy()
    save_csv(uncertain[out_cols], out / "uncertain_for_review.csv",
             f"manual review band ({high_recall_t}–{high_precision_t})")

    # ── Output 4: audit sample of predicted irrelevant ────────────────────────
    irr = df[df["review_bucket"] == "candidate_irrelevant"].copy()
    n_sample = min(audit_sample_n, len(irr))
    audit = irr.sample(n=n_sample, random_state=42) if n_sample > 0 else irr
    save_csv(audit[out_cols], out / "sample_predicted_irrelevant_for_audit.csv",
             f"random sample of {n_sample} predicted-irrelevant (false-negative check)")

    # ── Summary ───────────────────────────────────────────────────────────────
    bucket_counts = df["review_bucket"].value_counts().to_dict()
    summary = {
        "input_file":     input_path,
        "model_path":     model_path,
        "model_type":     model_type,
        "representation": repr_name,
        "thresholds": {
            "high_recall_t":    high_recall_t,
            "high_precision_t": high_precision_t,
        },
        "total_rescreened":    len(df),
        "candidate_relevant":  int(bucket_counts.get("candidate_relevant", 0)),
        "manual_review":       int(bucket_counts.get("manual_review", 0)),
        "candidate_irrelevant": int(bucket_counts.get("candidate_irrelevant", 0)),
    }
    save_json(summary, out / "rescreen_summary.json", "rescreen summary")
    print(f"\nDone. Buckets: {bucket_counts}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Apply best trained classifier to rejected articles."
    )
    p.add_argument("--input",    required=True,
                   help="CSV with title, article_text columns")
    p.add_argument("--model",    required=True,
                   help="Path to saved model (.joblib or HF model dir)")
    p.add_argument("--config",   default=None,
                   help="Path to model config JSON (auto-detected if omitted)")
    p.add_argument("--output-dir", default="reports/model_training")
    p.add_argument("--high-recall-t",    type=float, default=DEFAULT_HIGH_RECALL_T)
    p.add_argument("--high-precision-t", type=float, default=DEFAULT_HIGH_PRECISION_T)
    p.add_argument("--audit-sample-n",   type=int,   default=20)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    rescreen(
        input_path       = args.input,
        model_path       = args.model,
        config_path      = args.config,
        output_dir       = args.output_dir,
        high_recall_t    = args.high_recall_t,
        high_precision_t = args.high_precision_t,
        audit_sample_n   = args.audit_sample_n,
    )


if __name__ == "__main__":
    main()
