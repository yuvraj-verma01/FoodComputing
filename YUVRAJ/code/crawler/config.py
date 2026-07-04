"""Configuration loading, validation, and access helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Project root is one level above this file (news_crawler/)
BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Loads config.yaml and exposes typed accessors.

    API keys are overlaid from environment variables so secrets
    never live in YAML.
    """

    def __init__(self, config_path: Optional[str | Path] = None) -> None:
        if config_path is None:
            config_path = BASE_DIR / "config" / "config.yaml"
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with config_path.open(encoding="utf-8") as fh:
            self._cfg: dict = yaml.safe_load(fh) or {}

        self._overlay_env_api_keys()
        self._resolve_relative_paths()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _overlay_env_api_keys(self) -> None:
        keys = self._cfg.setdefault("api_keys", {})
        env_map = {
            "GOOGLE_CSE_KEY": "google_cse_key",
            "GOOGLE_CSE_CX": "google_cse_cx",
            "BING_API_KEY": "bing_api_key",
            "SERPAPI_KEY": "serpapi_key",
            "MEDIACLOUD_API_KEY": "mediacloud_key",
        }
        for env_var, cfg_key in env_map.items():
            val = os.getenv(env_var, "")
            if val:
                keys[cfg_key] = val

        # Auto-enable search backends when their key is present
        disc = self._cfg.setdefault("discovery", {})
        search = disc.setdefault("search_api", {})
        if keys.get("google_cse_key") and keys.get("google_cse_cx"):
            search.setdefault("google_cse", {})["enabled"] = True
        if keys.get("bing_api_key"):
            search.setdefault("bing", {})["enabled"] = True
        if keys.get("serpapi_key"):
            search.setdefault("serpapi", {})["enabled"] = True

    def _resolve_relative_paths(self) -> None:
        """Convert relative path values to absolute paths rooted at BASE_DIR."""
        for key, val in self._cfg.get("paths", {}).items():
            p = Path(val)
            if not p.is_absolute():
                self._cfg["paths"][key] = str(BASE_DIR / p)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get(self, *keys: str, default: Any = None) -> Any:
        """Drill into nested dict by successive keys."""
        val: Any = self._cfg
        for k in keys:
            if not isinstance(val, dict):
                return default
            val = val.get(k)
            if val is None:
                return default
        return val

    def path(self, key: str) -> Path:
        """Return a Path for a named path entry; create dir if needed."""
        raw = self.get("paths", key)
        if raw is None:
            raise KeyError(f"No path configured for '{key}'")
        p = Path(raw)
        # If key ends with a known file extension, make the parent dir
        if p.suffix in {".db", ".jsonl", ".csv", ".json", ".log"}:
            p.parent.mkdir(parents=True, exist_ok=True)
        else:
            p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def food_terms(self) -> list[str]:
        return self.get("food_terms") or []

    @property
    def adulteration_terms(self) -> list[str]:
        return self.get("adulteration_terms") or []

    @property
    def action_terms(self) -> list[str]:
        return self.get("action_terms") or []

    @property
    def location_terms(self) -> list[str]:
        return self.get("location_terms") or []

    @property
    def date_start(self) -> str:
        return self.get("date_range", "start") or "2021-01-01"

    @property
    def date_end(self) -> str:
        return self.get("date_range", "end") or "2026-12-31"

    @property
    def crawl_delay(self) -> float:
        return float(self.get("crawl", "delay_seconds") or 2.5)

    @property
    def user_agent(self) -> str:
        return self.get("crawl", "user_agent") or "FoodResearchBot/1.0"

    @property
    def raw(self) -> dict:
        return self._cfg

    def __repr__(self) -> str:
        return f"Config(food_terms={len(self.food_terms)}, date={self.date_start}–{self.date_end})"
