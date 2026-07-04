"""Optional: fine-tune a Hugging Face transformer for binary relevance classification.

Models supported
----------------
- distilbert-base-uncased
- microsoft/deberta-v3-small

Gated behind --include-hf flag in run_all_experiments.py.
Dataset is small (≤320 rows with text), so:
  - early stopping on validation loss
  - weight decay regularisation
  - 5-fold stratified CV with a smaller model to avoid over-fitting
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .evaluate_models import compute_metrics, tune_thresholds

HF_MODELS = ["distilbert-base-uncased", "microsoft/deberta-v3-small"]
MAX_LENGTH = 256  # tokens — balances coverage vs. speed for 256-512 word articles


def _check_hf_available() -> bool:
    try:
        import torch          # noqa: F401
        import transformers   # noqa: F401
        return True
    except ImportError:
        return False


def fine_tune_one_fold(
    model_name: str,
    X_train: list[str],
    y_train: list[int],
    X_val: list[str],
    y_val: list[int],
    output_dir: Path,
    max_epochs: int = 6,
    patience: int = 2,
    batch_size: int = 8,
    lr: float = 2e-5,
    weight_decay: float = 0.01,
) -> tuple[list[int], list[float]]:
    """Fine-tune for one fold; return (val_preds, val_probas)."""
    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=2, ignore_mismatched_sizes=True
    )

    # Class weights for imbalanced data
    n_pos = sum(y_train)
    n_neg = len(y_train) - n_pos
    pos_weight = n_neg / max(n_pos, 1)
    class_weights = torch.tensor([1.0, pos_weight], dtype=torch.float32).to(device)
    model = model.to(device)

    class TextDataset(Dataset):
        def __init__(self, texts, labels):
            self.enc = tokenizer(
                texts, truncation=True, padding=True,
                max_length=MAX_LENGTH, return_tensors="pt"
            )
            self.labels = torch.tensor(labels, dtype=torch.long)

        def __len__(self):
            return len(self.labels)

        def __getitem__(self, idx):
            return {k: v[idx] for k, v in self.enc.items()}, self.labels[idx]

    train_ds = TextDataset(X_train, y_train)
    val_ds   = TextDataset(X_val,   y_val)
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_dl   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn   = torch.nn.CrossEntropyLoss(weight=class_weights)

    best_val_loss = float("inf")
    patience_count = 0
    best_state = None

    for epoch in range(max_epochs):
        model.train()
        for batch, labels_b in train_dl:
            batch = {k: v.to(device) for k, v in batch.items()}
            labels_b = labels_b.to(device)
            logits = model(**batch).logits
            loss = loss_fn(logits, labels_b)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # Validation loss for early stopping
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch, labels_b in val_dl:
                batch = {k: v.to(device) for k, v in batch.items()}
                labels_b = labels_b.to(device)
                logits = model(**batch).logits
                val_loss += loss_fn(logits, labels_b).item()
        val_loss /= max(len(val_dl), 1)

        if val_loss < best_val_loss - 1e-4:
            best_val_loss = val_loss
            patience_count = 0
            import copy
            best_state = copy.deepcopy(model.state_dict())
        else:
            patience_count += 1
            if patience_count >= patience:
                break

    if best_state:
        model.load_state_dict(best_state)

    # Predict on validation fold
    model.eval()
    all_probas: list[float] = []
    all_preds:  list[int]   = []
    with torch.no_grad():
        for batch, _ in val_dl:
            batch = {k: v.to(device) for k, v in batch.items()}
            logits = model(**batch).logits
            probs  = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
            preds  = (probs >= 0.5).astype(int)
            all_probas.extend(probs.tolist())
            all_preds.extend(preds.tolist())

    return all_preds, all_probas


def train_and_evaluate_hf(
    representations: dict[str, list[str]],
    labels: np.ndarray,
    df_meta: pd.DataFrame,
    output_dir: Path,
    hf_model_names: Optional[list[str]] = None,
    target_repr_names: Optional[list[str]] = None,
    n_splits: int = 5,
) -> list[dict]:
    """Stratified CV fine-tuning for HF transformers.

    Only runs on representations in target_repr_names (default: keyword windows + body).
    Returns list of CV result dicts.
    """
    if not _check_hf_available():
        warnings.warn(
            "torch and transformers are not installed. "
            "Skipping HF transformer training. "
            "Install with: pip install torch transformers"
        )
        return []

    from sklearn.model_selection import StratifiedKFold

    hf_model_names    = hf_model_names    or ["distilbert-base-uncased"]
    target_repr_names = target_repr_names or [
        "title_plus_keyword_windows", "title_plus_body"
    ]

    models_dir = output_dir / "trained_models"
    models_dir.mkdir(parents=True, exist_ok=True)

    cv_results: list[dict] = []

    for hf_model in hf_model_names:
        safe_name = hf_model.replace("/", "_")
        for repr_name in target_repr_names:
            if repr_name not in representations:
                continue
            texts = representations[repr_name]
            model_name = f"hf_{safe_name}"

            print(f"  HF CV: {model_name} × {repr_name} (this may take a while) ...")

            skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
            all_indices: list[int] = []
            all_true:    list[int] = []
            all_pred:    list[int] = []
            all_proba:   list[float] = []

            for fold_idx, (train_idx, test_idx) in enumerate(skf.split(texts, labels)):
                print(f"    Fold {fold_idx+1}/{n_splits} ...", flush=True)
                X_train = [texts[i] for i in train_idx]
                X_val   = [texts[i] for i in test_idx]
                y_train = labels[train_idx].tolist()
                y_val   = labels[test_idx].tolist()

                import torch as _torch
                _batch = 32 if _torch.cuda.is_available() else 8
                try:
                    preds, probas = fine_tune_one_fold(
                        hf_model, X_train, y_train, X_val, y_val, output_dir,
                        batch_size=_batch,
                    )
                except Exception as exc:
                    warnings.warn(f"HF fold {fold_idx+1} failed: {exc}")
                    preds  = [0] * len(test_idx)
                    probas = [0.0] * len(test_idx)

                all_indices.extend(test_idx.tolist())
                all_true.extend(y_val)
                all_pred.extend(preds)
                all_proba.extend(probas)

            order = np.argsort(all_indices)
            all_true_arr  = np.array(all_true)[order]
            all_pred_arr  = np.array(all_pred)[order]
            all_proba_arr = np.array(all_proba)[order]

            metrics    = compute_metrics(all_true_arr, all_pred_arr, all_proba_arr)
            thresholds = tune_thresholds(all_true_arr, all_proba_arr)
            m = metrics
            print(
                f"  HF {model_name} × {repr_name}: "
                f"F1={m['f1']:.3f}  Rec={m['recall']:.3f}  "
                f"ROC-AUC={m.get('roc_auc', float('nan')):.3f}"
            )

            records = []
            for orig_idx, true, pred, prob in zip(
                np.array(all_indices)[order], all_true_arr, all_pred_arr, all_proba_arr
            ):
                row = df_meta.iloc[orig_idx]
                records.append({
                    "article_id": row.get("article_id", f"row_{orig_idx}"),
                    "title": row.get("title", ""),
                    "url": row.get("url", ""),
                    "true_label": int(true),
                    "predicted_label": int(pred),
                    "predicted_probability": float(prob),
                    "model_name": model_name,
                    "representation": repr_name,
                })

            cv_results.append({
                "model_name":   model_name,
                "representation": repr_name,
                "metrics":      metrics,
                "thresholds":   thresholds,
                "predictions_df": pd.DataFrame(records),
                "all_true":     all_true_arr,
                "all_pred":     all_pred_arr,
                "all_proba":    all_proba_arr,
            })

            # Save the model config so rescreen_rejected_urls can reference it
            cfg = {
                "model_type":     "hf_transformer",
                "hf_model_name":  hf_model,
                "representation": repr_name,
                "max_length":     MAX_LENGTH,
            }
            config_path = models_dir / f"{safe_name}_{repr_name}_config.json"
            config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    return cv_results
