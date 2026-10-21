import json
import os
from functools import lru_cache
from pathlib import Path


def catalog_path() -> Path:
    override = os.environ.get("LANGUAGES_CATALOG")
    if override:
        return Path(override)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "shared" / "languages.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("shared/languages.json")


@lru_cache
def load_catalog() -> dict:
    return json.loads(catalog_path().read_text(encoding="utf-8"))
