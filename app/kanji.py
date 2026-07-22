from __future__ import annotations

import re

import requests

from app.models import KanjiGloss

API = "https://kanjiapi.dev/v1/kanji/"

# kanjiapi.dev lists KANJIDIC meanings in a fixed order that is not ranked by
# everyday frequency, so the first entry is sometimes an obscure gloss (e.g. 子
# leads with "11PM-1AM", the zodiac hour of the rat). Drop those obviously
# non-semantic meanings so the "Kanji used" block shows something useful.
_JUNK_MEANING = re.compile(
    r"\d\s*(?:AM|PM)|sign of|zodiac|counter for|^nth\b|^\d+(?:st|nd|rd|th)\b",
    re.IGNORECASE,
)


def is_kanji(ch: str) -> bool:
    code = ord(ch)
    return (0x3400 <= code <= 0x9FFF) or (0xF900 <= code <= 0xFAFF)


def extract_kanji(word: str) -> list[str]:
    seen: list[str] = []
    for ch in word:
        if is_kanji(ch) and ch not in seen:
            seen.append(ch)
    return seen


def parse_meaning(data: dict, limit: int = 2) -> str:
    meanings = data.get("meanings") or []
    good = [m for m in meanings if not _JUNK_MEANING.search(m)]
    chosen = (good or meanings)[:limit]
    return "; ".join(chosen)


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
