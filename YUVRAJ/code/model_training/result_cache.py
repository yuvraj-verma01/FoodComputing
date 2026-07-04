"""Resumable per-model result cache.

Every completed model's CV result dict (metrics, thresholds, out-of-fold
probabilities, predictions DataFrame) is pickled the moment it finishes, into
  <output_dir>/_run_state/results/<key>.pkl

On restart the orchestrator loads whatever is already there and skips those
models — so an interrupted run (laptop sleep / move / shutdown) resumes from the
last finished model instead of starting over.

Embedding matrices are cached separately as .npz so encoders are not re-run.
"""

from __future__ import annotations

import pickle
import re
from pathlib import Path

import numpy as np


def _key(model_name: str, repr_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.+-]", "_", f"{model_name}__{repr_name}")


def results_dir(output_dir: Path) -> Path:
    d = Path(output_dir) / "_run_state" / "results"
    d.mkdir(parents=True, exist_ok=True)
    return d


def emb_dir(output_dir: Path) -> Path:
    d = Path(output_dir) / "_run_state" / "embeddings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def result_path(output_dir: Path, model_name: str, repr_name: str) -> Path:
    return results_dir(output_dir) / f"{_key(model_name, repr_name)}.pkl"


def has_result(output_dir: Path, model_name: str, repr_name: str) -> bool:
    return result_path(output_dir, model_name, repr_name).exists()


def load_result(output_dir: Path, model_name: str, repr_name: str) -> dict | None:
    p = result_path(output_dir, model_name, repr_name)
    if not p.exists():
        return None
    try:
        with p.open("rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def save_result(output_dir: Path, result: dict) -> None:
    p = result_path(output_dir, result["model_name"], result["representation"])
    tmp = p.with_suffix(".tmp")
    with tmp.open("wb") as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(p)  # atomic — a half-written file can never be loaded


def load_all_results(output_dir: Path) -> list[dict]:
    out = []
    for p in sorted(results_dir(output_dir).glob("*.pkl")):
        try:
            with p.open("rb") as f:
                out.append(pickle.load(f))
        except Exception:
            pass
    return out


# ── Embedding-matrix cache ────────────────────────────────────────────────────

def emb_path(output_dir: Path, encoder_key: str, repr_name: str) -> Path:
    return emb_dir(output_dir) / f"{_key(encoder_key, repr_name)}.npz"


def load_matrix(output_dir: Path, encoder_key: str, repr_name: str) -> np.ndarray | None:
    p = emb_path(output_dir, encoder_key, repr_name)
    if not p.exists():
        return None
    try:
        return np.load(p)["matrix"]
    except Exception:
        return None


def save_matrix(output_dir: Path, encoder_key: str, repr_name: str, matrix: np.ndarray) -> None:
    p = emb_path(output_dir, encoder_key, repr_name)
    tmp = p.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, matrix=matrix)
    tmp.replace(p)
