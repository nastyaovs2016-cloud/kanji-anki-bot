from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

MODEL_ID = 1608310002
IMMERSIONKIT_MEDIA_BASE = "https://us-southeast-1.linodeobjects.com/immersionkit/media"

_DATA_DIR = Path(__file__).parent / "data"


@dataclass
class Settings:
    bot_token: str
    ocr_api_key: str
    owner_id: int
    deck_names: list[str]


def settings() -> Settings:
    raw_decks = os.environ.get("DECK_NAMES", "Default")
    deck_names = [d.strip() for d in raw_decks.split(",") if d.strip()]
    return Settings(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        ocr_api_key=os.environ.get("OCR_SPACE_API_KEY", ""),
        owner_id=int(os.environ.get("ALLOWED_TELEGRAM_USER_ID", "0") or "0"),
        deck_names=deck_names,
    )


@lru_cache(maxsize=1)
def load_deck_map() -> dict:
    with open(_DATA_DIR / "immersionkit_decks.json", encoding="utf-8") as f:
        return json.load(f)
