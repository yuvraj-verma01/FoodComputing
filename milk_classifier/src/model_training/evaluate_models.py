"""Stratified CV, metrics computation, and Excel exporter."""
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, average_precision_score, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score
)

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray = None):
    """Compute precision, recall, F1, ROC-AUC, PR-AUC for Class 1 (Adulterated Milk)."""
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
        "roc_auc": float("nan"),
        "pr_auc": float("nan"),
    }
    
    if y_proba is not None and len(np.unique(y_true)) > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba))
        metrics["pr_auc"] = float(average_precision_score(y_true, y_proba))
        
    return metrics

def export_results_to_excel(
    results: list[dict],
    best_f1_result: dict,
    excel_path: str = "milk_adulteration_model_results.xlsx"
) -> None:
    """Exports model comparison, CV predictions, and error analysis into a multi-sheet Excel file."""
    # Sheet 1: Model Comparison Table
    summary_rows = []
    for r in results:
        m = r["metrics"]
        summary_rows.append({
            "Model Name": r["model_name"],
            "Representation": r["representation"],
            "F1-Score": round(m["f1"], 4),
            "Precision": round(m["precision"], 4),
            "Recall": round(m["recall"], 4),
            "ROC-AUC": round(m["roc_auc"], 4) if not np.isnan(m["roc_auc"]) else None,
            "PR-AUC": round(m["pr_auc"], 4) if not np.isnan(m["pr_auc"]) else None,
            "Accuracy": round(m["accuracy"], 4),
            "True Positive (TP)": m["tp"],
            "False Positive (FP)": m["fp"],
            "False Negative (FN)": m["fn"],
            "True Negative (TN)": m["tn"],
        })
        
    df_metrics = pd.DataFrame(summary_rows).sort_values("F1-Score", ascending=False)
    
    # Sheet 2: Out-of-Fold Cross Validation Predictions (Best Model)
    df_preds = best_f1_result.get("predictions_df", pd.DataFrame())
    
    # Sheet 3 & 4: False Positives & False Negatives (Best Model)
    if not df_preds.empty:
        df_fp = df_preds[(df_preds["true_label"] == 0) & (df_preds["predicted_label"] == 1)]
        df_fn = df_preds[(df_preds["true_label"] == 1) & (df_preds["predicted_label"] == 0)]
    else:
        df_fp = pd.DataFrame()
        df_fn = pd.DataFrame()
        
    # Write to Excel
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_metrics.to_excel(writer, sheet_name="Model Metrics Comparison", index=False)
        if not df_preds.empty:
            df_preds.to_excel(writer, sheet_name="Best Model Predictions", index=False)
        if not df_fp.empty:
            df_fp.to_excel(writer, sheet_name="False Positives", index=False)
        if not df_fn.empty:
            df_fn.to_excel(writer, sheet_name="False Negatives", index=False)
            
    print(f"\n[SUCCESS] Final evaluation results saved to Excel: {excel_path}")

def select_best_models(results: list[dict]) -> tuple[dict, dict]:
    """Select the best models based on F1 and Recall."""
    best_f1 = max(results, key=lambda x: x["metrics"]["f1"])
    best_recall = max(results, key=lambda x: x["metrics"]["recall"])
    return best_f1, best_recall
