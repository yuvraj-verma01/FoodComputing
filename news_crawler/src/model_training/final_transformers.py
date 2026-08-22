"""Final-run fine-tuned transformers.

3 transformers × 3 modes  +  Longformer  = 10 models.

Transformers : distilbert-base-uncased, roberta-base, microsoft/deberta-v3-small
Modes
  lead_512        title+body truncated to first 512 tokens
  oil_window_512  title + oil-window text, max 512 tokens
  chunk_pool_full full article → ≤4 chunks of 512 → CLS vectors → mean+max pool → head

Longformer : allenai/longformer-base-4096, full article up to 4096 tokens, global
             attention on [CLS].

All folds use StratifiedKFold(n_splits, shuffle=True, random_state=42); fp16
autocast + gradient accumulation to fit a 6 GB GPU.
"""

from __future__ import annotations

import copy
import gc
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from . import result_cache as rc
from .evaluate_models import compute_metrics, tune_thresholds

CHUNK_LEN  = 512
MAX_CHUNKS = 4   # 4 * 512 = 2048 tokens


def _check_hf() -> bool:
    try:
        import torch          # noqa: F401
        import transformers   # noqa: F401
        return True
    except ImportError:
        return False


# ── chunk_pool_full ───────────────────────────────────────────────────────────

def _build_chunks(texts, labels, tokenizer, max_chunks, chunk_len):
    import torch
    cls = tokenizer.cls_token_id if tokenizer.cls_token_id is not None else tokenizer.bos_token_id
    sep = tokenizer.sep_token_id if tokenizer.sep_token_id is not None else tokenizer.eos_token_id
    pad = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
    body = chunk_len - 2

    A_ids, A_mask, A_cmask = [], [], []
    for text in texts:
        ids = tokenizer(text, truncation=True, max_length=max_chunks * chunk_len,
                        add_special_tokens=False)["input_ids"]
        c_ids, c_mask = [], []
        for i in range(0, max(len(ids), 1), body):
            piece = ids[i:i + body]
            seq = [cls] + piece + [sep]
            attn = [1] * len(seq)
            seq += [pad] * (chunk_len - len(seq))
            attn += [0] * (chunk_len - len(attn))
            c_ids.append(seq); c_mask.append(attn)
            if len(c_ids) >= max_chunks:
                break
        cmask = [1] * len(c_ids)
        while len(c_ids) < max_chunks:
            c_ids.append([pad] * chunk_len); c_mask.append([0] * chunk_len); cmask.append(0)
        A_ids.append(c_ids); A_mask.append(c_mask); A_cmask.append(cmask)

    return (torch.tensor(A_ids), torch.tensor(A_mask),
            torch.tensor(A_cmask, dtype=torch.float32), torch.tensor(labels))


def _ft_chunkpool(model_name, Xtr, ytr, Xval, yval,
                  max_epochs=6, patience=2, batch_size=2, accum=4,
                  lr=2e-5, weight_decay=0.01, save_path=None):
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import AutoModel, AutoTokenizer

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(model_name)
    backbone = AutoModel.from_pretrained(model_name)
    H = backbone.config.hidden_size

    class Net(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = backbone
            self.dropout = torch.nn.Dropout(0.1)
            self.head = torch.nn.Linear(2 * H, 2)  # mean ⊕ max

        def forward(self, ids, mask, cmask):
            b, c, l = ids.shape
            out = self.backbone(input_ids=ids.view(b * c, l),
                                attention_mask=mask.view(b * c, l))
            cls = out.last_hidden_state[:, 0, :].view(b, c, -1)
            cm = cmask.unsqueeze(-1)
            mean = (cls * cm).sum(1) / cm.sum(1).clamp(min=1.0)
            masked = cls.masked_fill(cm == 0, float("-inf"))
            mx = masked.max(1).values
            mx = torch.nan_to_num(mx, neginf=0.0)
            return self.head(self.dropout(torch.cat([mean, mx], dim=1)))

    net = Net().to(dev)
    n_pos = sum(ytr); n_neg = len(ytr) - n_pos
    w = torch.tensor([1.0, n_neg / max(n_pos, 1)], dtype=torch.float32).to(dev)
    loss_fn = torch.nn.CrossEntropyLoss(weight=w)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=weight_decay)
    scaler = torch.cuda.amp.GradScaler(enabled=dev.type == "cuda")

    tr = _build_chunks(Xtr, ytr, tok, MAX_CHUNKS, CHUNK_LEN)
    vl = _build_chunks(Xval, yval, tok, MAX_CHUNKS, CHUNK_LEN)
    trdl = DataLoader(TensorDataset(*tr), batch_size=batch_size, shuffle=True)
    vldl = DataLoader(TensorDataset(*vl), batch_size=batch_size, shuffle=False)

    best, state, bad = float("inf"), None, 0
    for _ in range(max_epochs):
        net.train(); opt.zero_grad()
        for s, (ids, mask, cmask, yb) in enumerate(trdl):
            ids, mask, cmask, yb = ids.to(dev), mask.to(dev), cmask.to(dev), yb.to(dev)
            with torch.autocast(device_type=dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                loss = loss_fn(net(ids, mask, cmask), yb) / accum
            scaler.scale(loss).backward()
            if (s + 1) % accum == 0:
                scaler.step(opt); scaler.update(); opt.zero_grad()
        net.eval(); vloss = 0.0
        with torch.no_grad():
            for ids, mask, cmask, yb in vldl:
                ids, mask, cmask, yb = ids.to(dev), mask.to(dev), cmask.to(dev), yb.to(dev)
                with torch.autocast(device_type=dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                    vloss += loss_fn(net(ids, mask, cmask), yb).item()
        vloss /= max(len(vldl), 1)
        if vloss < best - 1e-4:
            best, state, bad = vloss, copy.deepcopy(net.state_dict()), 0
        else:
            bad += 1
            if bad >= patience:
                break
    if state:
        net.load_state_dict(state)

    net.eval(); probs = []
    with torch.no_grad():
        for ids, mask, cmask, _ in vldl:
            ids, mask, cmask = ids.to(dev), mask.to(dev), cmask.to(dev)
            with torch.autocast(device_type=dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                p = torch.softmax(net(ids, mask, cmask).float(), 1)[:, 1]
            probs.extend(p.cpu().numpy().tolist())

    if save_path is not None:
        sp = Path(save_path); sp.mkdir(parents=True, exist_ok=True)
        torch.save(net.state_dict(), sp / "chunkpool_state.pt")
        tok.save_pretrained(sp)
        (sp / "chunkpool_config.json").write_text(json.dumps({
            "backbone": model_name, "hidden_size": H, "pooling": "mean+max",
            "max_chunks": MAX_CHUNKS, "chunk_len": CHUNK_LEN,
        }, indent=2), encoding="utf-8")

    del net, backbone; gc.collect()
    if dev.type == "cuda":
        torch.cuda.empty_cache()
    return [int(p >= 0.5) for p in probs], probs


# ── single-window: lead_512 / oil_window_512 / longformer ─────────────────────

def _ft_single(model_name, Xtr, ytr, Xval, yval, max_length=512, max_epochs=6,
               patience=2, batch_size=8, accum=1, lr=2e-5, weight_decay=0.01,
               global_cls=False, save_path=None):
    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=2, ignore_mismatched_sizes=True).to(dev)

    n_pos = sum(ytr); n_neg = len(ytr) - n_pos
    w = torch.tensor([1.0, n_neg / max(n_pos, 1)], dtype=torch.float32).to(dev)
    loss_fn = torch.nn.CrossEntropyLoss(weight=w)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scaler = torch.cuda.amp.GradScaler(enabled=dev.type == "cuda")

    class DS(Dataset):
        def __init__(self, texts, labels):
            self.enc = tok(texts, truncation=True, padding="max_length",
                           max_length=max_length, return_tensors="pt")
            self.labels = torch.tensor(labels)
        def __len__(self): return len(self.labels)
        def __getitem__(self, i): return {k: v[i] for k, v in self.enc.items()}, self.labels[i]

    trdl = DataLoader(DS(Xtr, ytr), batch_size=batch_size, shuffle=True)
    vldl = DataLoader(DS(Xval, yval), batch_size=batch_size, shuffle=False)

    def glob(b):
        if global_cls:
            g = torch.zeros_like(b["input_ids"]); g[:, 0] = 1
            b["global_attention_mask"] = g
        return b

    best, state, bad = float("inf"), None, 0
    for _ in range(max_epochs):
        model.train(); opt.zero_grad()
        for s, (b, yb) in enumerate(trdl):
            b = glob({k: v.to(dev) for k, v in b.items()}); yb = yb.to(dev)
            with torch.autocast(device_type=dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                loss = loss_fn(model(**b).logits, yb) / accum
            scaler.scale(loss).backward()
            if (s + 1) % accum == 0:
                scaler.step(opt); scaler.update(); opt.zero_grad()
        model.eval(); vloss = 0.0
        with torch.no_grad():
            for b, yb in vldl:
                b = glob({k: v.to(dev) for k, v in b.items()}); yb = yb.to(dev)
                with torch.autocast(device_type=dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                    vloss += loss_fn(model(**b).logits, yb).item()
        vloss /= max(len(vldl), 1)
        if vloss < best - 1e-4:
            best, state, bad = vloss, copy.deepcopy(model.state_dict()), 0
        else:
            bad += 1
            if bad >= patience:
                break
    if state:
        model.load_state_dict(state)

    model.eval(); probs = []
    with torch.no_grad():
        for b, _ in vldl:
            b = glob({k: v.to(dev) for k, v in b.items()})
            with torch.autocast(device_type=dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                p = torch.softmax(model(**b).logits.float(), 1)[:, 1]
            probs.extend(p.cpu().numpy().tolist())

    if save_path is not None:
        sp = Path(save_path); sp.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(sp)
        tok.save_pretrained(sp)
        (sp / "mode_config.json").write_text(json.dumps({
            "backbone": model_name, "max_length": max_length,
            "global_cls": global_cls,
        }, indent=2), encoding="utf-8")

    del model; gc.collect()
    if dev.type == "cuda":
        torch.cuda.empty_cache()
    return [int(p >= 0.5) for p in probs], probs


# ── CV driver ─────────────────────────────────────────────────────────────────

def _run_cv(fold_fn, texts, labels, df_meta, model_name, repr_name, n_splits, ckpt_path=None):
    from sklearn.model_selection import StratifiedKFold
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    idxs, trues, preds, probas = [], [], [], []
    for k, (tr, te) in enumerate(skf.split(texts, labels)):
        print(f"    Fold {k+1}/{n_splits} ...", flush=True)
        Xtr = [texts[i] for i in tr]; Xte = [texts[i] for i in te]
        ytr = labels[tr].tolist(); yte = labels[te].tolist()
        # Save a deployable checkpoint on the final fold (no extra training).
        sp = ckpt_path if (ckpt_path is not None and k == n_splits - 1) else None
        try:
            p, pr = fold_fn(Xtr, ytr, Xte, yte, sp)
        except Exception as exc:
            warnings.warn(f"{model_name} fold {k+1} failed: {exc}")
            p, pr = [0] * len(te), [0.0] * len(te)
        idxs.extend(te.tolist()); trues.extend(yte); preds.extend(p); probas.extend(pr)

    order = np.argsort(idxs)
    yt = np.array(trues)[order]; yp = np.array(preds)[order]; pb = np.array(probas)[order]
    metrics = compute_metrics(yt, yp, pb)
    print(f"  {model_name} × {repr_name}: F1={metrics['f1']:.3f}  "
          f"R={metrics['recall']:.3f}  ROC-AUC={metrics.get('roc_auc', float('nan')):.3f}")

    records = []
    for oi, t, p, pr in zip(np.array(idxs)[order], yt, yp, pb):
        row = df_meta.iloc[oi]
        records.append({"article_id": row.get("article_id", f"row_{oi}"),
                        "title": row.get("title", ""), "url": row.get("url", ""),
                        "true_label": int(t), "predicted_label": int(p),
                        "predicted_probability": float(pr),
                        "model_name": model_name, "representation": repr_name})
    return {"model_name": model_name, "representation": repr_name, "metrics": metrics,
            "thresholds": tune_thresholds(yt, pb), "predictions_df": pd.DataFrame(records),
            "all_true": yt, "all_pred": yp, "all_proba": pb}


def train_and_evaluate_final_transformers(
    full_texts: list[str],
    oil_window_texts: list[str],
    labels: np.ndarray,
    df_meta: pd.DataFrame,
    output_dir: Path,
    n_splits: int = 5,
    bert_models=None,
    include_longformer: bool = True,
) -> list[dict]:
    if not _check_hf():
        warnings.warn("torch/transformers unavailable — skipping transformers.")
        return []

    ckpt_root = Path(output_dir) / "trained_models" / "final_checkpoints" / "transformers"
    ckpt_root.mkdir(parents=True, exist_ok=True)
    bert_models = bert_models or ["distilbert-base-uncased", "roberta-base",
                                  "microsoft/deberta-v3-small"]
    results = []

    def run_one(fold_fn, texts, model_name, repr_name):
        cached = rc.load_result(output_dir, model_name, repr_name)
        if cached is not None:
            print(f"  [cached] {model_name} × {repr_name}  F1={cached['metrics']['f1']:.3f}")
            results.append(cached)
            return
        res = _run_cv(fold_fn, texts, labels, df_meta, model_name, repr_name,
                      n_splits, ckpt_path=ckpt_root / model_name)
        rc.save_result(output_dir, res)
        results.append(res)

    for hf in bert_models:
        short = hf.split("/")[-1]
        print(f"\n  >>> {short} — lead_512")
        run_one(lambda a, b, c, d, sp, _hf=hf: _ft_single(_hf, a, b, c, d, max_length=512, batch_size=8, save_path=sp),
                full_texts, f"hf_{short}_lead_512", "title_plus_body_full")
        print(f"\n  >>> {short} — oil_window_512")
        run_one(lambda a, b, c, d, sp, _hf=hf: _ft_single(_hf, a, b, c, d, max_length=512, batch_size=8, save_path=sp),
                oil_window_texts, f"hf_{short}_oil_window_512", "title_plus_oil_windows")
        print(f"\n  >>> {short} — chunk_pool_full")
        run_one(lambda a, b, c, d, sp, _hf=hf: _ft_chunkpool(_hf, a, b, c, d, save_path=sp),
                full_texts, f"hf_{short}_chunk_pool_full", "title_plus_body_full")

    if include_longformer:
        print(f"\n  >>> longformer-base-4096 — full article @ 4096 tok")
        run_one(lambda a, b, c, d, sp: _ft_single("allenai/longformer-base-4096", a, b, c, d,
                                                  max_length=4096, batch_size=1, accum=8,
                                                  global_cls=True, save_path=sp),
                full_texts, "hf_longformer_full", "title_plus_body_full")

    return results
