from __future__ import annotations

import hashlib

import requests

JPOD_URL = "https://assets.languagepod101.com/dictionary/japanese/audiomp3.php"
GTTS_URL = "https://translate.google.com/translate_tts"

# Missing words return a fixed "audio not available" placeholder mp3 (verified
# 2026-07-23): 52288 bytes, this md5. Detect it so we can fall back to TTS.
_PLACEHOLDER_MD5 = "7e2c2f954ef6051373ba916f000168dc"

# Some CDNs/APIs block non-browser User-Agents from server IPs; present a browser
# UA (same approach as app/immersionkit.py).
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def is_placeholder(content: bytes) -> bool:
    return hashlib.md5(content).hexdigest() == _PLACEHOLDER_MD5


def _fetch_native(word: str, reading: str) -> bytes | None:
    try:
        r = requests.get(
            JPOD_URL,
            params={"kanji": word, "kana": reading},
            headers=_HEADERS,
            timeout=20,
        )
    except requests.RequestException:
        return None
    if r.status_code == 200 and r.content and not is_placeholder(r.content):
        return r.content
    return None


def _fetch_tts(word: str) -> bytes | None:
    try:
        r = requests.get(
            GTTS_URL,
            params={"ie": "UTF-8", "q": word, "tl": "ja", "client": "tw-ob"},
            headers={**_HEADERS, "Referer": "https://translate.google.com/"},
            timeout=20,
        )
    except requests.RequestException:
        return None
    if r.status_code == 200 and r.content:
        return r.content
    return None


def fetch_word_audio(word: str, reading: str) -> bytes | None:
    native = _fetch_native(word, reading)
    if native is not None:
        return native
    return _fetch_tts(word)
