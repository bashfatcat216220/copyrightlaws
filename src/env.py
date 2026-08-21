"""Minimal .env loader (stdlib only — no python-dotenv dependency).

Reads KEY=VALUE lines from the repo-root .env (gitignored) into os.environ WITHOUT
overriding variables already set in the real environment. Call load_env() before
checking os.environ for ANTHROPIC_API_KEY / COURTLISTENER_API_TOKEN / GOVINFO_API_KEY.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("'\"")
        if k and k not in os.environ:
            os.environ[k] = v
