"""Load and save the mock JSON database."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "mock_db.json"


def load_db(path: Path | None = None) -> dict[str, list]:
    resolved = path or DEFAULT_DB_PATH
    with open(resolved, encoding="utf-8") as handle:
        return json.load(handle)


def save_db(db: dict[str, list], path: Path | None = None) -> None:
    resolved = path or DEFAULT_DB_PATH
    with open(resolved, "w", encoding="utf-8") as handle:
        json.dump(db, handle, indent=2, ensure_ascii=False)
