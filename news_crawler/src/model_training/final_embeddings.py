"""Final-run full-article embedding models.

4 encoders × 3 representations × 3 classifiers = 36 models.

Encoders
  minilm     sentence-transformers/all-MiniLM-L6-v2
  mpnet      sentence-transformers/all-mpnet-base-v2
  e5-large   intfloat/e5-large-v2          (per-chunk prefix "passage: ")
  bge-large  BAAI/bge-large-en-v1.5

Representations (per encoder)
  full_chunk_mean       512-token chunks of the full article, mean-pooled
  full_chunk_max        512-token chunks of the full article, max-pooled
  oil_window_embedding  embed title + oil-window text (single vector)

Classifiers
  lr       LogisticRegression       (class_weight=balanced)
  linsvm   LinearSVC (calibrated)   (class_weight=balanced)
  rbfsvm   SVC rbf   (probability)  (class_weight=balanced)
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, LinearSVC

from . import result_cache as rc
from .evaluate_models import cross_validate_model

EMBED_MODELS = {
    "minilm":    ("sentence-transformers/all-MiniLM-L6-v2", ""),
    "mpnet":     ("sentence-transformers/all-mpnet-base-v2", ""),
    "e5-large":  ("intfloat/e5-large-v2",                   "passage: "),
    "bge-large": ("BAAI/bge-large-en-v1.5",                 ""),
}

CHUNK_TOKENS = 512
MAX_CHUNKS   = 8   # 8 * 512 = 4096 tokens — covers every article fully


def _make_lr():
    return LogisticRegression(class_weight="balanced", max_iter=2000, C=1.0,
                              solver="lbfgs", random_state=42)


def _make_linsvm():
    return CalibratedClassifierCV(
        LinearSVC(class_weight="balanced", max_iter=5000, C=1.0, random_state=42),
        cv=3, method="sigmoid")


def _make_rbfsvm():
    return SVC(kernel="rbf", class_weight="balanced", C=1.0, gamma="scale",
               probability=True, random_state=42)


CLASSIFIERS = {"lr": _make_lr, "linsvm": _make_linsvm, "rbfsvm": _make_rbfsvm}


def _token_chunks(text: str, tokenizer, chunk_tokens: int, max_chunks: int) -> list[str]:
    """Split text into <=chunk_tokens token windows, decoded back to strings."""
    ids = tokenizer.encode(text, add_special_tokens=False)
    if not ids:
        return [""]
    chunks = []
    for i in range(0, len(ids), chunk_tokens):
        piece = ids[i:i + chunk_tokens]
        chunks.append(tokenizer.decode(piece, skip_special_tokens=True))
        if len(chunks) >= max_chunks:
            break
    return chunks


def _encode_chunks_pool(texts, model, prefix, pool):
    """Per-document pooled embedding ('mean' or 'max') over 512-token chunks."""
    tokenizer = model.tokenizer
    all_chunks, owner = [], []
    for di, text in enumerate(texts):
        for ch in _token_chunks(text, tokenizer, CHUNK_TOKENS, MAX_CHUNKS):
            all_chunks.append(prefix + ch)
            owner.append(di)

    vecs = model.encode(all_chunks, batch_size=32, show_progress_bar=True,
                        convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)
    dim = vecs.shape[1]
    out = (np.zeros((len(texts), dim), np.float32) if pool == "mean"
           else np.full((len(texts), dim), -np.inf, np.float32))
    counts = np.zeros(len(texts), np.int32)
    for v, di in zip(vecs, owner):
        if pool == "mean":
            out[di] += v
        else:
            np.maximum(out[di], v, out=out[di])
        counts[di] += 1
    if pool == "mean":
        counts[counts == 0] = 1
        out /= counts[:, None]
    else:
        out[~np.isfinite(out)] = 0.0
    return out


def _encode_single(texts, model, prefix):
    """One embedding per document (encoder truncates internally at 512 tokens)."""
    return model.encode([prefix + t for t in texts], batch_size=32,
                        show_progress_bar=True, convert_to_numpy=True,
                        normalize_embeddings=True).astype(np.float32)


def load_encoder(hf_name: str):
    from sentence_transformers import SentenceTransformer
    print(f"  Loading encoder: {hf_name}")
    m = SentenceTransformer(hf_name)
    m.max_seq_length = CHUNK_TOKENS
    return m


def train_and_evaluate_final_embeddings(
    full_texts: list[str],
    oil_window_texts: list[str],
    labels: np.ndarray,
    df_meta: pd.DataFrame,
    output_dir: Path,
    n_splits: int = 5,
) -> list[dict]:
    ckpt_dir = Path(output_dir) / "trained_models" / "final_checkpoints" / "embeddings"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    repr_specs = {
        "full_chunk_mean":      ("full", "mean"),
        "full_chunk_max":       ("full", "max"),
        "oil_window_embedding": ("oil",  "single"),
    }

    for key, (hf_name, prefix) in EMBED_MODELS.items():
        # Skip the whole encoder if every (repr × clf) result is already cached.
        all_done = all(
            rc.has_result(output_dir, f"emb_{key}_{clf}", repr_name)
            for repr_name in repr_specs for clf in CLASSIFIERS
        )
        if all_done:
            print(f"  [cached] all 9 models for encoder {key} — skipping encode.")
            for repr_name in repr_specs:
                for clf in CLASSIFIERS:
                    results.append(rc.load_result(output_dir, f"emb_{key}_{clf}", repr_name))
            continue

        enc = None  # lazy-load only if needed
        for repr_name, (src, pool) in repr_specs.items():
            # matrix (cached or freshly encoded)
            mat = rc.load_matrix(output_dir, key, repr_name)
            if mat is None:
                if enc is None:
                    enc = load_encoder(hf_name)
                if src == "full":
                    mat = _encode_chunks_pool(full_texts, enc, prefix, pool)
                else:
                    mat = _encode_single(oil_window_texts, enc, prefix)
                rc.save_matrix(output_dir, key, repr_name, mat)

            scaler = StandardScaler()
            mat_scaled = scaler.fit_transform(mat)

            for clf_name, factory in CLASSIFIERS.items():
                model_name = f"emb_{key}_{clf_name}"
                cached = rc.load_result(output_dir, model_name, repr_name)
                if cached is not None:
                    print(f"  [cached] {model_name} × {repr_name}  F1={cached['metrics']['f1']:.3f}")
                    results.append(cached)
                    continue

                print(f"  CV: {model_name} × {repr_name} ...", end=" ", flush=True)
                result = cross_validate_model(
                    estimator=factory(), X=mat_scaled, y=labels, df_meta=df_meta,
                    model_name=model_name, repr_name=repr_name, n_splits=n_splits)
                m = result["metrics"]
                print(f"F1={m['f1']:.3f}  P={m['precision']:.3f}  "
                      f"R={m['recall']:.3f}  ROC-AUC={m.get('roc_auc', float('nan')):.3f}")

                # Deployable checkpoint: refit classifier on full matrix + save scaler/config.
                full_clf = factory(); full_clf.fit(mat_scaled, labels)
                stem = f"{model_name}__{repr_name}"
                joblib.dump(full_clf, ckpt_dir / f"{stem}_clf.joblib")
                joblib.dump(scaler,   ckpt_dir / f"{stem}_scaler.joblib")
                import json
                (ckpt_dir / f"{stem}_config.json").write_text(json.dumps({
                    "encoder": hf_name, "encoder_prefix": prefix, "classifier": clf_name,
                    "representation": repr_name, "chunk_tokens": CHUNK_TOKENS,
                    "max_chunks": MAX_CHUNKS, "pool": pool,
                }, indent=2), encoding="utf-8")

                rc.save_result(output_dir, result)
                results.append(result)

        if enc is not None:
            del enc
            try:
                import torch; torch.cuda.empty_cache()
            except Exception:
                pass

    return results
