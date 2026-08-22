"""Shared data loading, validation, and I/O utilities."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ── Data loading ──────────────────────────────────────────────────────────────

def load_and_validate(
    input_path: str,
    title_col: str = "title",
    text_col: str = "article_text",
    label_col: str = "keep",
    url_col: str = "url",
    date_col: str = "date",
    source_col: str = "source",
    round_col: str = "round_number",
    id_col: str = "article_id",
) -> pd.DataFrame:
    """Load CSV, validate required columns, drop bad rows, return clean DataFrame.

    Standard internal column names after loading:
        title, article_text, label, url, date, source, round, article_id
    """
    p = Path(input_path)
    if not p.exists():
        sys.exit(f"ERROR: Input file not found: {input_path}")

    df = pd.read_csv(p, low_memory=False)
    print(f"Loaded {len(df):,} rows from {p.name}")

    # Validate required columns are present under their user-specified names
    required_actual = {title_col, text_col, label_col}
    missing = required_actual - set(df.columns)
    if missing:
        sys.exit(
            f"ERROR: Missing required columns: {sorted(missing)}\n"
            f"Available columns: {sorted(df.columns.tolist())}\n"
            f"Use --title-column, --text-column, --label-column to remap."
        )

    # Build rename map: actual_name -> standard_internal_name
    rename: dict[str, str] = {}
    if title_col != "title":
        rename[title_col] = "title"
    if text_col != "article_text":
        rename[text_col] = "article_text"
    rename[label_col] = "label"  # always map to "label"

    # Optional columns — rename only if present and not already at target name
    for actual, standard in [
        (url_col, "url"),
        (date_col, "date"),
        (source_col, "source"),
        (round_col, "round"),
        (id_col, "article_id"),
    ]:
        if actual and actual in df.columns and actual != standard:
            rename[actual] = standard

    rename = {k: v for k, v in rename.items() if k != v}  # drop self-assignments
    df = df.rename(columns=rename)

    # Fill in article_id if absent
    if "article_id" not in df.columns:
        df["article_id"] = [str(uuid.uuid4()) for _ in range(len(df))]

    # Ensure title is a non-null string
    df["title"] = df["title"].fillna("").astype(str).str.strip()

    # Drop rows with missing/empty article_text
    df["article_text"] = df["article_text"].fillna("").astype(str).str.strip()
    n_before = len(df)
    df = df[df["article_text"] != ""].copy()
    dropped = n_before - len(df)
    if dropped:
        print(f"Dropped {dropped:,} rows with missing/empty article_text.")

    # Validate label values
    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    bad = df["label"].isna() | ~df["label"].isin([0, 1])
    if bad.any():
        sys.exit(
            f"ERROR: 'label' column has {bad.sum()} non-0/1 values "
            f"(after mapping from '{label_col}'). Values must be exactly 0 or 1."
        )
    df["label"] = df["label"].astype(int)

    # Require both classes
    counts = df["label"].value_counts().to_dict()
    if counts.get(0, 0) == 0 or counts.get(1, 0) == 0:
        sys.exit(
            f"ERROR: Dataset must contain both classes (0 and 1). "
            f"Found: {counts}"
        )

    print(
        f"Clean dataset: {len(df):,} rows | "
        f"relevant (1) = {counts.get(1, 0):,} | "
        f"irrelevant (0) = {counts.get(0, 0):,}"
    )
    return df.reset_index(drop=True)


def print_dataset_stats(df: pd.DataFrame) -> None:
    counts = df["label"].value_counts().to_dict()
    total = len(df)
    print(f"  Total: {total} | Relevant: {counts.get(1, 0)} "
          f"({100*counts.get(1,0)/max(total,1):.1f}%) | "
          f"Irrelevant: {counts.get(0, 0)}")
    if "round" in df.columns:
        by_round = df.groupby("round")["label"].value_counts().unstack(fill_value=0)
        print(f"  By round:\n{by_round.to_string()}")


# ── Saving ────────────────────────────────────────────────────────────────────

def save_csv(df: pd.DataFrame, path: Path, label: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    tag = f" [{label}]" if label else ""
    print(f"  Saved{tag}: {path.name}  ({len(df):,} rows)")


def save_json(data: dict, path: Path, label: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tag = f" [{label}]" if label else ""
    print(f"  Saved{tag}: {path.name}")


# ── Misc helpers ──────────────────────────────────────────────────────────────

def get_article_id(row: pd.Series, fallback_idx: int) -> str:
    val = row.get("article_id", "")
    return str(val).strip() if val and str(val).strip() not in ("", "nan") else f"row_{fallback_idx}"


def safe_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def classification_label(prob: float, high_recall_t: float, high_precision_t: float) -> str:
    """Map a probability to a review bucket label."""
    if prob >= high_precision_t:
        return "candidate_relevant"
    if prob >= high_recall_t:
        return "manual_review"
    return "candidate_irrelevant"
