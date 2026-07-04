"""Run Round 4 MediaCloud discovery + relevance pipeline end-to-end.

Steps:
  1. MediaCloud discovery: 28 queries, all 28 India collections
  2. Oil relevance pipeline: metadata -> crawl -> rules -> outputs (LLM skipped)
     - Deduplicates against 4,281 previously-seen URLs
     - crawl_priority fixed: phrase/boolean adjacent_or_unclear -> medium (not drop)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ROUND4_RUN = "edible_oil_adulteration_round_04_2026-06-25"
RUN_DIR   = ROOT / "data" / "runs" / ROUND4_RUN
CONFIG    = ROOT / "config" / "config_edible_oils_round4.yaml"
QUERY_PLAN = RUN_DIR / "proposed_mediacloud_round4_seed_queries.csv"
PREV_RUN  = ROOT / "data" / "runs" / "edible_oil_adulteration_round_03_2026-06-23"


def run(cmd: list[str]) -> None:
    print("\n" + "=" * 80)
    print("RUN:", " ".join(str(c) for c in cmd))
    print("=" * 80)
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    run([
        sys.executable, "scripts/run_combined_mediacloud_discovery.py",
        "--config", str(CONFIG),
        "--query-plan", str(QUERY_PLAN),
        "--run-dir", str(RUN_DIR),
        "--baseline-run-dir", str(PREV_RUN),
    ])

    run([
        sys.executable, "scripts/run_oil_relevance_pipeline.py",
        "--config", str(CONFIG),
        "--run-dir", str(RUN_DIR),
        "--stage", "all",
        "--skip-llm",
    ])

    print(f"\nRound 4 complete. Outputs at: {RUN_DIR / 'mediacloud' / 'outputs' / 'oil_relevance'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
