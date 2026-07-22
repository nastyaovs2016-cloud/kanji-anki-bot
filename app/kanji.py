from __future__ import annotations

import requests

from app.models import KanjiGloss

API = "https://kanjiapi.dev/v1/kanji/"


def is_kanji(ch: str) -> bool:
    code = ord(ch)
    return (0x3400 <= code <= 0x9FFF) or (0xF900 <= code <= 0xFAFF)


def extract_kanji(word: str) -> list[str]:
    seen: list[str] = []
    for ch in word:
        if is_kanji(ch) and ch not in seen:
            seen.append(ch)
    return seen


def parse_meaning(data: dict) -> str:
    meanings = data.get("meanings") or []
    return meanings[0] if meanings else ""


def fetch_breakdown(word: str) -> list[KanjiGloss]:
    result: list[KanjiGloss] = []
    for ch in extract_kanji(word):
        try:
            resp = requests.get(API + ch, timeout=20)
            if resp.status_code != 200:
                continue
            meaning = parse_meaning(resp.json())
        except requests.RequestException:
            continue
        if meaning:
            result.append(KanjiGloss(char=ch, meaning=meaning))
    return result
