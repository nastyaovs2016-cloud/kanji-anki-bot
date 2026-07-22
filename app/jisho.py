from __future__ import annotations

import requests

from app.models import WordInfo

API = "https://jisho.org/api/v1/search/words"


def parse_word(data: dict) -> WordInfo | None:
    entries = data.get("data") or []
    if not entries:
        return None
    first = entries[0]
    japanese = (first.get("japanese") or [{}])[0]
    word = japanese.get("word") or japanese.get("reading") or ""
    reading = japanese.get("reading") or ""
    meanings = [
        s["english_definitions"]
        for s in first.get("senses", [])
        if s.get("english_definitions")
    ]
    return WordInfo(word=word, reading=reading, meanings=meanings)


def fetch_word(word: str) -> WordInfo | None:
    resp = requests.get(API, params={"keyword": word}, timeout=20)
    resp.raise_for_status()
    return parse_word(resp.json())
