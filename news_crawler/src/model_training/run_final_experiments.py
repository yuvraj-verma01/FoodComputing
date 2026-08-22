"""FINAL model run — single comprehensive comparison.

Blocks (all on the same corpus, labels, 5 stratified folds, seed 42):
  1. TF-IDF (word1-2 ⊕ char3-5)         : 2 clf × 3 repr  = 6
  2. Full-article embeddings            : 4 enc × 3 repr × 3 clf = 36
  3. Fine-tuned transformers            : 3 × 3 modes = 9
  4. Longformer-4096                    : 1
  5. Ensembles (OOF avg + weighted)     : 6 pairs × {avg, weighted} ≈ 12

Outputs (to --output-dir):
  model_comparison.csv, best_model_summary.json,
  false_positives.csv, false_negatives.csv, cross_validation_predictions.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from src.model_training.build_text_representations import build_final_representations
from src.model_training.evaluate_models import (
    compute_metrics, extract_false_cases, results_to_comparison_df,
    select_best_models, tune_thresholds,
)
from src.model_training.final_tfidf import train_and_evaluate_final_tfidf
from src.model_training.final_embeddings import train_and_evaluate_final_embeddings
from src.model_training.final_transformers import train_and_evaluate_final_transformers
from src.model_training.utils import load_and_validate, print_dataset_stats, save_csv, save_json

WEIGHT_GRID = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

# representations counted as "oil-window" vs "full-article" for ensemble #6
OIL_WINDOW_REPRS = {"title_plus_oil_windows", "oil_window_embedding"}
FULL_ARTICLE_REPRS = {"title_plus_body_full", "full_chunk_mean", "full_chunk_max"}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--label-column", default="final_keep")
    p.add_argument("--output-dir", default="reports/model_training")
    p.add_argument("--n-splits", type=int, default=5)
    p.add_argument("--skip-embeddings", action="store_true")
    p.add_argument("--skip-transformers", action="store_true")
    p.add_argument("--skip-longformer", action="store_true")
    return p.parse_args()


# ── Ensemble helpers ──────────────────────────────────────────────────────────

def _result_from_probas(name, repr_tag, y_true, avg_proba, df_meta):
    preds = (avg_proba >= 0.5).astype(int)
    metrics = compute_metrics(y_true, preds, avg_proba)
    records = []
    for i in range(len(y_true)):
        row = df_meta.iloc[i]
        records.append({"article_id": row.get("article_id", f"row_{i}"),
                        "title": row.get("title", ""), "url": row.get("url", ""),
                        "true_label": int(y_true[i]), "predicted_label": int(preds[i]),
                        "predicted_probability": float(avg_proba[i]),
                        "model_name": name, "representation": repr_tag})
    return {"model_name": name, "representation": repr_tag, "metrics": metrics,
            "thresholds": tune_thresholds(y_true, avg_proba),
            "predictions_df": pd.DataFrame(records),
            "all_true": y_true, "all_pred": preds, "all_proba": avg_proba}


def _stack(members):
    return [np.asarray(m["all_proba"], dtype=float) for m in members]


_REPR_ABBR = {
    "title_plus_body_full": "full", "title_plus_oil_windows": "oilwin",
    "title_plus_keyword_windows": "kwwin", "full_chunk_mean": "cmean",
    "full_chunk_max": "cmax", "oil_window_embedding": "oilemb",
}


def _member_label(m):
    base = m["model_name"].replace("hf_", "").replace("emb_", "")
    return f"{base}/{_REPR_ABBR.get(m['representation'], m['representation'])}"


def make_average(members, df_meta, tag):
    if len(members) < 2:
        return None
    ref = members[0]["all_true"]
    for m in members[1:]:
        if not np.array_equal(m["all_true"], ref):
            print(f"  [WARN] label-order mismatch in {tag}; skipping.")
            return None
    avg = np.mean(_stack(members), axis=0)
    short = "+".join(_member_label(m) for m in members)
    r = _result_from_probas(f"ens_avg[{short}]", tag, ref, avg, df_meta)
    print(f"  {r['model_name']}: F1={r['metrics']['f1']:.3f}  "
          f"PR-AUC={r['metrics']['pr_auc']:.3f}  Rec={r['metrics']['recall']:.3f}")
    return r


def make_weighted(members, df_meta, tag):
    """Grid-search weights from WEIGHT_GRID, pick best by F1."""
    if len(members) < 2:
        return None
    ref = members[0]["all_true"]
    for m in members[1:]:
        if not np.array_equal(m["all_true"], ref):
            return None
    P = _stack(members)
    best = None
    for combo in product(WEIGHT_GRID, repeat=len(members)):
        w = np.array(combo, dtype=float)
        if w.sum() == 0:
            continue
        w = w / w.sum()
        avg = np.average(P, axis=0, weights=w)
        f1 = compute_metrics(ref, (avg >= 0.5).astype(int))["f1"]
        if best is None or f1 > best[0]:
            best = (f1, w, avg)
    _, w, avg = best
    short = "+".join(_member_label(m) for m in members)
    wtag = ",".join(f"{x:.2f}" for x in w)
    r = _result_from_probas(f"ens_wavg[{short}|{wtag}]", tag, ref, avg, df_meta)
    print(f"  {r['model_name']}: F1={r['metrics']['f1']:.3f}  "
          f"PR-AUC={r['metrics']['pr_auc']:.3f}  Rec={r['metrics']['recall']:.3f}")
    return r


def best_of(results, predicate):
    pool = [r for r in results if predicate(r) and r.get("all_proba") is not None]
    return max(pool, key=lambda r: r["metrics"]["f1"]) if pool else None


def main() -> int:
    args = _parse_args()
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("  Edible Oil Adulteration — FINAL MODEL RUN")
    print("=" * 72)

    df = load_and_validate(input_path=args.input, label_col=args.label_column)
    print_dataset_stats(df)
    labels = df["label"].values

    print("\nBuilding the 3 representations ...")
    reps = build_final_representations(df)
    full_texts = reps["title_plus_body_full"]
    oil_texts  = reps["title_plus_oil_windows"]
    wc = [len(t.split()) for t in full_texts]
    print(f"  full article: avg {sum(wc)//len(wc)} words, max {max(wc)} words")

    results: list[dict] = []

    # 1. TF-IDF
    print(f"\n{'─'*64}\n1. TF-IDF (word1-2 ⊕ char3-5) — 6 models\n{'─'*64}")
    results += train_and_evaluate_final_tfidf(reps, labels, df, out, args.n_splits)

    # 2. Embeddings
    if not args.skip_embeddings:
        print(f"\n{'─'*64}\n2. Full-article embeddings — 36 models\n{'─'*64}")
        results += train_and_evaluate_final_embeddings(
            full_texts, oil_texts, labels, df, out, args.n_splits)

    # 3 & 4. Transformers + Longformer
    if not args.skip_transformers:
        print(f"\n{'─'*64}\n3+4. Transformers (9) + Longformer (1)\n{'─'*64}")
        results += train_and_evaluate_final_transformers(
            full_texts, oil_texts, labels, df, out, args.n_splits,
            include_longformer=not args.skip_longformer)

    # 5. Ensembles
    print(f"\n{'─'*64}\n5. Ensembles (OOF average + weighted grid)\n{'─'*64}")
    best_tfidf = best_of(results, lambda r: r["model_name"].startswith("tfidf_"))
    best_emb   = best_of(results, lambda r: r["model_name"].startswith("emb_"))
    best_tf    = best_of(results, lambda r: r["model_name"].startswith("hf_") and "longformer" not in r["model_name"])
    best_long  = best_of(results, lambda r: "longformer" in r["model_name"])
    best_oilwin = best_of(results, lambda r: r["representation"] in OIL_WINDOW_REPRS)
    best_full   = best_of(results, lambda r: r["representation"] in FULL_ARTICLE_REPRS)

    pairs = [
        ("tfidf+emb",        [best_tfidf, best_emb]),
        ("tfidf+transf",     [best_tfidf, best_tf]),
        ("tfidf+longformer", [best_tfidf, best_long]),
        ("emb+transf",       [best_emb, best_tf]),
        ("tfidf+emb+transf", [best_tfidf, best_emb, best_tf]),
        ("oilwin+fullart",   [best_oilwin, best_full]),
    ]
    for tag, members in pairs:
        members = [m for m in members if m is not None]
        # de-dup if the same model+representation is "best" in two roles
        seen, uniq = set(), []
        for m in members:
            key = (m["model_name"], m["representation"])
            if key not in seen:
                seen.add(key); uniq.append(m)
        if len(uniq) < 2:
            continue
        a = make_average(uniq, df, f"ensemble:{tag}")
        w = make_weighted(uniq, df, f"ensemble:{tag}")
        if a: results.append(a)
        if w: results.append(w)

    # 6. Comparison + outputs
    print(f"\n{'─'*64}\nResults (sorted by F1)\n{'─'*64}")
    comp = results_to_comparison_df(results)
    print(comp[["model_name", "representation", "precision", "recall",
                "f1", "roc_auc", "pr_auc"]].to_string(index=False))
    save_csv(comp, out / "model_comparison.csv", "model comparison")

    best_f1, best_recall = select_best_models(results)
    print(f"\n  Best F1    : {best_f1['model_name']} × {best_f1['representation']}  "
          f"F1={best_f1['metrics']['f1']:.3f}")
    print(f"  Best Recall: {best_recall['model_name']} × {best_recall['representation']}  "
          f"Rec={best_recall['metrics']['recall']:.3f}")

    pred_dfs = [r["predictions_df"] for r in results if r.get("predictions_df") is not None]
    if pred_dfs:
        save_csv(pd.concat(pred_dfs, ignore_index=True),
                 out / "cross_validation_predictions.csv", "all CV predictions")

    fp_df, fn_df = extract_false_cases(best_f1)
    save_csv(fp_df, out / "false_positives.csv", "false positives (best F1)")
    save_csv(fn_df, out / "false_negatives.csv", "false negatives (best F1)")

    bm = best_f1["metrics"]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment": "final_full_article_run",
        "dataset": {"input_file": args.input, "total_rows": len(df),
                    "relevant": int((labels == 1).sum()),
                    "irrelevant": int((labels == 0).sum()),
                    "cv_folds": args.n_splits,
                    "avg_words": int(sum(wc)/len(wc)), "max_words": int(max(wc))},
        "n_models": len(results),
        "best_model_by_f1": {
            "model_name": best_f1["model_name"], "representation": best_f1["representation"],
            "accuracy": round(bm["accuracy"], 4), "precision": round(bm["precision"], 4),
            "recall": round(bm["recall"], 4), "f1": round(bm["f1"], 4),
            "roc_auc": round(bm.get("roc_auc", float("nan")), 4),
            "pr_auc": round(bm.get("pr_auc", float("nan")), 4),
            "thresholds": best_f1.get("thresholds", {})},
        "best_model_by_recall": {
            "model_name": best_recall["model_name"],
            "representation": best_recall["representation"],
            "recall": round(best_recall["metrics"]["recall"], 4),
            "f1": round(best_recall["metrics"]["f1"], 4)},
        "full_ranking": comp.to_dict(orient="records"),
    }
    save_json(summary, out / "best_model_summary.json", "best model summary")
    print(f"\nDone. {len(results)} models. Outputs in {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
