from __future__ import annotations

from urllib.parse import quote

import requests

from app.config import IMMERSIONKIT_MEDIA_BASE
from app.models import Example

API = "https://apiv2.immersionkit.com/search"


def parse_examples(data: dict) -> list[Example]:
    out: list[Example] = []
    for e in data.get("examples", []):
        image = e.get("image") or ""
        sound = e.get("sound") or ""
        out.append(
            Example(
                sentence=e.get("sentence", ""),
                sentence_furigana=e.get("sentence_with_furigana", "") or e.get("sentence", ""),
                translation=e.get("translation", ""),
                image_file=image,
                sound_file=sound,
                deck_id=e.get("title", ""),
            )
        )
    return out


def media_urls(ex, deck_map: dict) -> tuple[str | None, str | None]:
    deck = deck_map.get(ex.deck_id)
    if not deck:
        return (None, None)
    title = quote(deck["title"])
    category = deck["category"]

    def build(filename: str) -> str | None:
        if not filename:
            return None
        return f"{IMMERSIONKIT_MEDIA_BASE}/{category}/{title}/media/{quote(filename)}"

    return (build(ex.image_file), build(ex.sound_file))


def fetch_examples(word: str) -> list[Example]:
    resp = requests.get(
        API,
        params={"q": word, "sort": "sentence_length:asc", "category": "anime"},
        timeout=25,
    )
    resp.raise_for_status()
    return parse_examples(resp.json())
