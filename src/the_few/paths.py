"""Where personal data and config live — outside the repo.

Code is public (the repo). Your data is private: the SQLite store, your curated
source list, and any cron config live under a data home — by default
``~/.the-few/`` — so nothing personal is ever committed. Override with the
``THE_FEW_HOME`` environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_HOME = "THE_FEW_HOME"
DEFAULT_HOME = Path.home() / ".the-few"


def home() -> Path:
    """The data home directory (created on demand by `ensure_home`)."""
    return Path(os.environ.get(ENV_HOME) or DEFAULT_HOME).expanduser()


def db_path() -> Path:
    return home() / "the_few.db"


def sources_path() -> Path:
    return home() / "sources.toml"


def ensure_home() -> Path:
    h = home()
    h.mkdir(parents=True, exist_ok=True)
    return h
