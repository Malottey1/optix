"""Configuration from the environment, optionally loaded from a gitignored `.env` at the repo root.
Existing environment variables win; values are never printed or logged."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: str | Path | None = None) -> list:
    """Set variables from `.env` (KEY=VALUE lines, # comments) that are not already set.
    Returns the names it set (never the values)."""
    p = Path(path) if path else ROOT / ".env"
    if not p.is_file():
        return []
    names = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip().removeprefix("export ").strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v
            names.append(k)
    return names
