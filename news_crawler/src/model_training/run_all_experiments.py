"""CLI entry point — trains and evaluates all classifiers.

Usage
-----
python -m src.model_training.run_all_experiments \\
    --input  reports/master_corpus/master_all_articles.csv \\
    --label-column final_keep \\
    --output-dir reports/model_training

Add --include-hf to also fine-tune HuggingFace transformer models (slow, needs GPU).
Add --skip-sbert to skip sentence-transformer models (if not installed).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.stdout.reconfigure(encoding="utf-8")

from src.model_training.build_text_representations import build_representations
from src.model_training.evaluate_models import (
    extract_false_cases,
    results_to_comparison_df,
    select_best_models,
)
from src.model_training.train_tfidf_models import train_and_evaluate_tfidf
from src.model_training.utils import (
    load_and_validate,
    print_dataset_stats,
    save_csv,
    save_json,
)


# ── Argument parsing ──────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train and compare relevance classifiers for the edible oil corpus."
    )
    p.add_argument("--input",        required=True,
                   help="Path to master corpus CSV")
    p.add_argument("--title-column",  default="title")
    p.add_argument("--text-column",   default="article_text")
    p.add_argument("--label-column",  default="keep",
                   help="Column name for binary label (0/1). "
                        "Use 'final_keep' for master_all_articles.csv")
    p.add_argument("--url-column",    default="url")
    p.add_argument("--date-column",   default="date")
    p.add_argument("--source-column", default="source")
    p.add_argument("--round-column",  default="round_number")
    p.add_argument("--id-column",     default="article_id")
    p.add_argument("--output-dir",    default="reports/model_training")
    p.add_argument("--n-splits",      type=int, default=5,
                   help="Number of stratified CV folds (default 5)")
    p.add_argument("--include-hf",    action="store_true",
                   help="Also fine-tune HuggingFace transformer models (slow)")
    p.add_argument("--skip-sbert",    action="store_true",
                   help="Skip sentence-transformers (if not installed)")
    p.add_argument("--hf-models",     nargs="+",
                   default=["distilbert-base-uncased"],
                   help="HF model names to fine-tune (only used with --include-hf)")
    return p.parse_args()


# ── Best model persistence ────────────────────────────────────────────────────

def _save_best_model(
    result: dict,
    label: str,
    output_dir: Path,
    representations: dict,
    labels: np.ndarray,
) -> Path:
    """Refit the best model on the full dataset and save it."""
    models_dir = output_dir / "trained_models"
    models_dir.mkdir(parents=True, exist_ok=True)

    model_name = result["model_name"]
    repr_name  = result["representation"]

    if model_name.startswith("hf_") or model_name == "sbert_lr":
        print(f"  Best {label} model is {model_name} — "
              f"full-dataset artifact already saved during training.")
        return models_dir

    # TF-IDF pipeline — refit on full data
    from src.model_training.train_tfidf_models import PIPELINE_FACTORIES
    if model_name not in PIPELINE_FACTORIES:
        print(f"  WARNING: Cannot refit {model_name} — factory not found.")
        return models_dir

    texts = representations[repr_name]
    pipeline = PIPELINE_FACTORIES[model_name]()
    pipeline.fit(texts, labels)

    model_path = models_dir / f"best_model_{label}.joblib"
    joblib.dump(pipeline, model_path)

    thresholds = result.get("thresholds") or {}
    config = {
        "model_type":      "tfidf_pipeline",
        "model_name":      model_name,
        "representation":  repr_name,
        "selection_criterion": label,
        "thresholds": {
            "high_recall":    thresholds.get("high_recall",    0.35),
            "balanced":       thresholds.get("balanced",       0.50),
            "high_precision": thresholds.get("high_precision", 0.65),
        },
    }
    config_path = models_dir / f"best_model_{label}_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    # Symlink / copy latest "best_model" if it's the f1 winner
    if label == "f1":
        best_path = models_dir / "best_model.joblib"
        best_cfg  = models_dir / "best_model_config.json"
        import shutil
        shutil.copy2(model_path,  best_path)
        shutil.copy2(config_path, best_cfg)
        print(f"  Saved best model (f1): {best_path.name}")

    return model_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = _parse_args()
    out  = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("  Edible Oil Adulteration — Classifier Training")
    print(f"  Input : {args.input}")
    print(f"  Output: {out}")
    print("=" * 65)

    # ── 1. Load data ──────────────────────────────────────────────────────────
    df = load_and_validate(
        input_path  = args.input,
        title_col   = args.title_column,
        text_col    = args.text_column,
        label_col   = args.label_column,
        url_col     = args.url_column,
        date_col    = args.date_column,
        source_col  = args.source_column,
        round_col   = args.round_column,
        id_col      = args.id_column,
    )
    print_dataset_stats(df)
    labels = df["label"].values

    # ── 2. Build text representations ─────────────────────────────────────────
    print("\nBuilding text representations ...")
    representations = build_representations(df)

    all_results: list[dict] = []

    # ── 3. TF-IDF models ──────────────────────────────────────────────────────
    print(f"\n{'─'*55}")
    print("TF-IDF models (3 architectures × 4 representations = 12 runs)")
    print(f"{'─'*55}")
    tfidf_results, feature_records = train_and_evaluate_tfidf(
        representations=representations,
        labels=labels,
        df_meta=df,
        output_dir=out,
        n_splits=args.n_splits,
    )
    all_results.extend(tfidf_results)

    # ── 4. SBERT models ───────────────────────────────────────────────────────
    if not args.skip_sbert:
        print(f"\n{'─'*55}")
        print("SBERT models (4 representations)")
        print(f"{'─'*55}")
        try:
            from src.model_training.train_sentencebert_models import (
                train_and_evaluate_sbert,
            )
            sbert_results = train_and_evaluate_sbert(
                representations=representations,
                labels=labels,
                df_meta=df,
                output_dir=out,
                n_splits=args.n_splits,
            )
            all_results.extend(sbert_results)
        except ImportError as exc:
            print(f"  SBERT skipped — {exc}")
    else:
        print("SBERT skipped (--skip-sbert).")

    # ── 5. Optional HF transformer ────────────────────────────────────────────
    if args.include_hf:
        print(f"\n{'─'*55}")
        print("HuggingFace transformer (optional, slow)")
        print(f"{'─'*55}")
        from src.model_training.train_hf_transformer_optional import (
            train_and_evaluate_hf,
        )
        hf_results = train_and_evaluate_hf(
            representations=representations,
            labels=labels,
            df_meta=df,
            output_dir=out,
            hf_model_names=args.hf_models,
            n_splits=args.n_splits,
        )
        all_results.extend(hf_results)

    if not all_results:
        print("ERROR: No models trained — nothing to save.")
        return 1

    # ── 6. Model comparison ───────────────────────────────────────────────────
    print(f"\n{'─'*55}")
    print("Results summary")
    print(f"{'─'*55}")
    comparison_df = results_to_comparison_df(all_results)
    print(comparison_df[["model_name", "representation", "precision",
                          "recall", "f1", "roc_auc"]].to_string(index=False))
    save_csv(comparison_df, out / "model_comparison.csv", "model comparison")

    # ── 7. Select best models ─────────────────────────────────────────────────
    best_f1, best_recall = select_best_models(all_results)
    print(f"\n  Best by F1    : {best_f1['model_name']} × "
          f"{best_f1['representation']}  F1={best_f1['metrics']['f1']:.3f}")
    print(f"  Best by Recall: {best_recall['model_name']} × "
          f"{best_recall['representation']}  Rec={best_recall['metrics']['recall']:.3f}")

    _save_best_model(best_f1,     "f1",     out, representations, labels)
    _save_best_model(best_recall, "recall", out, representations, labels)

    # ── 8. Per-sample CV predictions ──────────────────────────────────────────
    all_pred_dfs = [r["predictions_df"] for r in all_results if r.get("predictions_df") is not None]
    if all_pred_dfs:
        all_preds_df = pd.concat(all_pred_dfs, ignore_index=True)
        save_csv(all_preds_df, out / "cross_validation_predictions.csv",
                 "all CV predictions")

    # ── 9. False positives / negatives for best-F1 model ─────────────────────
    fp_df, fn_df = extract_false_cases(best_f1)
    save_csv(fp_df, out / "false_positives.csv",  "false positives (best F1 model)")
    save_csv(fn_df, out / "false_negatives.csv",  "false negatives (best F1 model)")

    # ── 10. Feature importance ─────────────────────────────────────────────────
    if feature_records:
        feat_df = pd.DataFrame(feature_records)
        save_csv(feat_df, out / "feature_importance.csv", "TF-IDF feature importance")

    # ── 11. Best model summary JSON ───────────────────────────────────────────
    best_m = best_f1["metrics"]
    summary = {
        "generated_at":        datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "input_file":      args.input,
            "total_rows":      len(df),
            "relevant_count":  int((labels == 1).sum()),
            "irrelevant_count": int((labels == 0).sum()),
            "cv_folds":        args.n_splits,
        },
        "best_model_by_f1": {
            "model_name":      best_f1["model_name"],
            "representation":  best_f1["representation"],
            "accuracy":        round(best_m["accuracy"],  4),
            "precision":       round(best_m["precision"], 4),
            "recall":          round(best_m["recall"],    4),
            "f1":              round(best_m["f1"],        4),
            "roc_auc":         round(best_m.get("roc_auc", float("nan")), 4),
            "pr_auc":          round(best_m.get("pr_auc",  float("nan")), 4),
            "thresholds":      best_f1.get("thresholds", {}),
            "artifact":        str(out / "trained_models" / "best_model.joblib"),
        },
        "best_model_by_recall": {
            "model_name":      best_recall["model_name"],
            "representation":  best_recall["representation"],
            "recall":          round(best_recall["metrics"]["recall"], 4),
            "f1":              round(best_recall["metrics"]["f1"],     4),
        },
        "decision_rule_example": {
            "description": (
                "Use best_model.joblib to predict_proba on new article text. "
                "Then apply thresholds: prob >= high_precision -> candidate_relevant; "
                "prob in [high_recall, high_precision) -> manual_review; "
                "prob < high_recall -> candidate_irrelevant."
            ),
        },
    }
    save_json(summary, out / "best_model_summary.json", "best model summary")

    print(f"\nAll outputs saved to: {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
