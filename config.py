"""Loads settings from the .env file.

Secrets live in .env (which .gitignore excludes) rather than in code, so an
API key can never be committed by accident. Anyone cloning this repo brings
their own key.
"""

import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env() -> None:
    """Reads .env into the process environment. Existing vars win."""
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def require(name: str) -> str:
    """Fetches a required setting, with a clear error if it's missing."""
    load_env()
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to {ENV_PATH}")
    return value
