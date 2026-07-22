# Kanji → Anki Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Telegram bot that turns a Japanese word (typed or photographed) into a ready-to-import Anki `.apkg` card matching the user's existing template, and lets the user pick the target deck.

**Architecture:** A single Python process runs a python-telegram-bot app in long-polling mode plus a tiny health HTTP server (port 7860 for Hugging Face). Incoming text/photo → optional OCR → three free JSON APIs (Jisho for meaning+reading, kanjiapi.dev for per-kanji gloss, ImmersionKit apiv2 for example+audio+image) → genanki builds a `.apkg` with embedded media → the file is sent back to the chat. Pure parsing/formatting functions are separated from I/O so they are unit-testable without network.

**Tech Stack:** Python 3.11, python-telegram-bot 21.x, genanki 0.13.x, requests 2.32.x, pytest. Hosted on a Hugging Face Docker Space (free, no card).

## Global Constraints

- **Deploy target** is Python 3.11 (the Docker base image `python:3.11-slim`), but the **local test interpreter is Python 3.9** in the repo's prepared virtualenv at `.venv` (already created, with all deps installed). Run every test/verify command through it: `.venv/bin/python -m pytest ...`. Wherever a task step says `python -m pytest` or `python -c ...`, run it as `.venv/bin/python -m pytest` / `.venv/bin/python -c` instead.
- **Every new `app/*.py` module MUST start with `from __future__ import annotations` as its first line** (before other imports). The code uses `X | None` union annotations, which require this on Python 3.9. This is mandatory and is not "extra" scope.
- Keep test output pristine: `pytest.ini` (created in Task 1) filters the benign `urllib3 NotOpenSSLWarning` emitted under LibreSSL. Do not add other warning filters.
- Python 3.11 (matches the Docker base image `python:3.11-slim`).
- No paid services. APIs used: jisho.org, kanjiapi.dev, apiv2.immersionkit.com, api.ocr.space (free key). Verified working 2026-07-22 — see `docs/superpowers/research/2026-07-22-api-findings.md`.
- ImmersionKit search endpoint: `GET https://apiv2.immersionkit.com/search?q=<word>&sort=sentence_length:asc&category=anime`. The parameter is `q` (not `keyword`); `sort` MUST include order (`sentence_length:asc`).
- ImmersionKit media URL: `https://us-southeast-1.linodeobjects.com/immersionkit/media/<category>/<DISPLAY_TITLE>/media/<filename>`, where `<DISPLAY_TITLE>` (URL-encoded) comes from the lookup table `app/data/immersionkit_decks.json` keyed by the example's snake_case `title`.
- The bot must ignore any user whose Telegram id is not the configured owner (`ALLOWED_TELEGRAM_USER_ID`) to protect the free OCR quota.
- All user-facing bot text is in Russian (the user's language).
- Fixed genanki ids (never change after release): `MODEL_ID = 1608310001`. Deck ids are derived deterministically from the deck name (see Task 6).
- A kanji character is any codepoint in CJK ranges U+3400–U+9FFF or U+F900–U+FAFF.

---

## File Structure

```
kanji-anki-bot/
  Dockerfile                      # HF Space image (Task 8)
  requirements.txt                # pinned deps (Task 1)
  README.md                       # deployment guide (Task 8)
  .env.example                    # documents required env vars (Task 1)
  app/
    __init__.py
    config.py                     # env vars + deck-name list + constants (Task 1)
    models.py                     # WordInfo, KanjiGloss, Example dataclasses (Task 2)
    jisho.py                      # meaning + reading (Task 2)
    kanji.py                      # per-kanji gloss via kanjiapi.dev (Task 3)
    immersionkit.py               # examples + media URL builder (Task 4)
    ocr.py                        # OCR.space client (Task 5)
    card.py                       # format helpers + genanki .apkg builder (Task 6)
    lookup.py                     # orchestration: word -> assembled card data (Task 7)
    handlers.py                   # Telegram conversation + inline keyboards (Task 7)
    main.py                       # PTB app wiring + health server (Task 8)
    data/
      immersionkit_decks.json     # deck id -> {title, category} (already committed)
  tests/
    fixtures/                     # real API responses (already committed)
      jisho_kyou.json
      kanjiapi_hi.json
      immersionkit_kyou.json
    test_config.py
    test_jisho.py
    test_kanji.py
    test_immersionkit.py
    test_ocr.py
    test_card.py
    test_lookup.py
    test_handlers.py
```

---

### Task 1: Project scaffolding, config, dependencies

**Files:**
- Create: `requirements.txt`, `.env.example`, `pytest.ini`, `app/__init__.py`, `app/config.py`
- Test: `tests/test_config.py`
- Existing (already committed): `app/data/immersionkit_decks.json`

**Interfaces:**
- Produces:
  - `app.config.settings()` → returns a `Settings` dataclass with fields:
    `bot_token: str`, `ocr_api_key: str`, `owner_id: int`, `deck_names: list[str]`.
    Reads env vars `TELEGRAM_BOT_TOKEN`, `OCR_SPACE_API_KEY`,
    `ALLOWED_TELEGRAM_USER_ID`, `DECK_NAMES` (comma-separated).
  - `app.config.MODEL_ID = 1608310001`
  - `app.config.IMMERSIONKIT_MEDIA_BASE = "https://us-southeast-1.linodeobjects.com/immersionkit/media"`
  - `app.config.load_deck_map()` → `dict[str, dict]` loaded from `app/data/immersionkit_decks.json`.

- [ ] **Step 1: Create `requirements.txt`**

```
python-telegram-bot==21.6
genanki==0.13.1
requests==2.32.3
pytest==8.3.3
```

- [ ] **Step 2: Create `.env.example`**

```
TELEGRAM_BOT_TOKEN=123456:ABC-your-bot-token-from-BotFather
OCR_SPACE_API_KEY=your-free-key-from-ocr.space
ALLOWED_TELEGRAM_USER_ID=000000000
DECK_NAMES=Японский::Слова,Японский::Кандзи,Default
```

- [ ] **Step 3: Create `app/__init__.py`** (empty file)

- [ ] **Step 3b: Create `pytest.ini`** (repo root)

```ini
[pytest]
filterwarnings =
    ignore::urllib3.exceptions.NotOpenSSLWarning
```

- [ ] **Step 4: Write the failing test** — `tests/test_config.py`

```python
import os
import app.config as config


def test_settings_parses_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("OCR_SPACE_API_KEY", "key")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_ID", "42")
    monkeypatch.setenv("DECK_NAMES", "A, B ,C")
    s = config.settings()
    assert s.bot_token == "tok"
    assert s.ocr_api_key == "key"
    assert s.owner_id == 42
    assert s.deck_names == ["A", "B", "C"]  # trimmed, split on comma


def test_deck_map_has_known_deck():
    m = config.load_deck_map()
    assert m["castle_in_the_sky"]["title"] == "Castle in the sky"
    assert m["castle_in_the_sky"]["category"] == "anime"
    assert len(m) >= 90
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL (ModuleNotFoundError / AttributeError: no `settings`).

- [ ] **Step 6: Write `app/config.py`**

```python
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

MODEL_ID = 1608310001
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
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .env.example app/__init__.py app/config.py tests/test_config.py
git commit -m "feat: project scaffolding, config, and deck map loader"
```

---

### Task 2: Jisho client (meaning + reading)

**Files:**
- Create: `app/models.py`, `app/jisho.py`
- Test: `tests/test_jisho.py`
- Fixture (committed): `tests/fixtures/jisho_kyou.json`

**Interfaces:**
- Produces:
  - `app.models.WordInfo` dataclass: `word: str`, `reading: str`, `meanings: list[list[str]]` (each inner list is one sense's glosses).
  - `app.jisho.parse_word(data: dict) -> WordInfo | None` — pure; `data` is the full Jisho JSON. Returns `None` if `data["data"]` is empty.
  - `app.jisho.fetch_word(word: str) -> WordInfo | None` — I/O; GETs the Jisho API and calls `parse_word`.

- [ ] **Step 1: Write the failing test** — `tests/test_jisho.py`

```python
import json
from pathlib import Path
from app.jisho import parse_word

FIX = Path(__file__).parent / "fixtures"


def test_parse_word_kyou():
    data = json.loads((FIX / "jisho_kyou.json").read_text(encoding="utf-8"))
    wi = parse_word(data)
    assert wi is not None
    assert wi.word == "今日"
    assert wi.reading == "きょう"
    # first sense contains "today"
    assert "today" in wi.meanings[0]
    assert len(wi.meanings) >= 1


def test_parse_word_empty_returns_none():
    assert parse_word({"data": []}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_jisho.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write `app/models.py`**

```python
from dataclasses import dataclass


@dataclass
class WordInfo:
    word: str
    reading: str
    meanings: list[list[str]]


@dataclass
class KanjiGloss:
    char: str
    meaning: str


@dataclass
class Example:
    sentence: str
    sentence_furigana: str
    translation: str
    image_file: str
    sound_file: str
    deck_id: str
```

- [ ] **Step 4: Write `app/jisho.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_jisho.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/jisho.py tests/test_jisho.py
git commit -m "feat: Jisho client for meaning and reading"
```

---

### Task 3: kanjiapi.dev client (per-kanji gloss)

**Files:**
- Create: `app/kanji.py`
- Test: `tests/test_kanji.py`
- Fixture (committed): `tests/fixtures/kanjiapi_hi.json`

**Interfaces:**
- Consumes: `app.models.KanjiGloss`.
- Produces:
  - `app.kanji.is_kanji(ch: str) -> bool`
  - `app.kanji.extract_kanji(word: str) -> list[str]` — unique kanji chars, order preserved.
  - `app.kanji.parse_meaning(data: dict) -> str` — first meaning from a kanjiapi response, or `""`.
  - `app.kanji.fetch_breakdown(word: str) -> list[KanjiGloss]` — I/O; one GET per kanji char; skips chars with no entry.

- [ ] **Step 1: Write the failing test** — `tests/test_kanji.py`

```python
import json
from pathlib import Path
from app.kanji import is_kanji, extract_kanji, parse_meaning

FIX = Path(__file__).parent / "fixtures"


def test_is_kanji():
    assert is_kanji("今") is True
    assert is_kanji("き") is False   # hiragana
    assert is_kanji("A") is False


def test_extract_kanji_dedups_and_keeps_order():
    assert extract_kanji("今日今") == ["今", "日"]
    assert extract_kanji("食べる") == ["食"]
    assert extract_kanji("きょう") == []


def test_parse_meaning_uses_first():
    data = json.loads((FIX / "kanjiapi_hi.json").read_text(encoding="utf-8"))
    assert parse_meaning(data) == data["meanings"][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kanji.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write `app/kanji.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_kanji.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/kanji.py tests/test_kanji.py
git commit -m "feat: per-kanji gloss via kanjiapi.dev"
```

---

### Task 4: ImmersionKit client + media URL builder

**Files:**
- Create: `app/immersionkit.py`
- Test: `tests/test_immersionkit.py`
- Fixture (committed): `tests/fixtures/immersionkit_kyou.json`

**Interfaces:**
- Consumes: `app.models.Example`, `app.config.load_deck_map`, `app.config.IMMERSIONKIT_MEDIA_BASE`.
- Produces:
  - `app.immersionkit.parse_examples(data: dict) -> list[Example]` — pure.
  - `app.immersionkit.media_urls(ex: Example, deck_map: dict) -> tuple[str | None, str | None]` — returns `(image_url, sound_url)`; `(None, None)` if the deck id is unknown. URL-encodes the display title.
  - `app.immersionkit.fetch_examples(word: str) -> list[Example]` — I/O; GET apiv2 search sorted shortest-first.

- [ ] **Step 1: Write the failing test** — `tests/test_immersionkit.py`

```python
import json
from pathlib import Path
from app.immersionkit import parse_examples, media_urls
from app.config import load_deck_map

FIX = Path(__file__).parent / "fixtures"


def test_parse_examples_fields():
    data = json.loads((FIX / "immersionkit_kyou.json").read_text(encoding="utf-8"))
    examples = parse_examples(data)
    assert len(examples) > 0
    ex = examples[0]
    assert ex.sentence
    assert "[" in ex.sentence_furigana        # furigana markup present
    assert ex.translation
    assert ex.image_file.endswith(".jpg")
    assert ex.sound_file.endswith(".mp3")
    assert ex.deck_id                          # snake_case title


def test_media_urls_builds_encoded_path():
    ex = type("E", (), {
        "image_file": "A_CastleInTheSky_1_0.6.32.395.jpg",
        "sound_file": "A_CastleInTheSky_1_0.6.31.200-0.6.33.590.mp3",
        "deck_id": "castle_in_the_sky",
    })()
    img, snd = media_urls(ex, load_deck_map())
    assert img == (
        "https://us-southeast-1.linodeobjects.com/immersionkit/media/"
        "anime/Castle%20in%20the%20sky/media/A_CastleInTheSky_1_0.6.32.395.jpg"
    )
    assert snd.endswith(".mp3")
    assert "Castle%20in%20the%20sky" in snd


def test_media_urls_unknown_deck_returns_none():
    ex = type("E", (), {"image_file": "x.jpg", "sound_file": "x.mp3", "deck_id": "nope"})()
    assert media_urls(ex, load_deck_map()) == (None, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_immersionkit.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write `app/immersionkit.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_immersionkit.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/immersionkit.py tests/test_immersionkit.py
git commit -m "feat: ImmersionKit client and media URL builder"
```

---

### Task 5: OCR.space client (photo → text)

**Files:**
- Create: `app/ocr.py`
- Test: `tests/test_ocr.py`

**Interfaces:**
- Produces:
  - `app.ocr.parse_ocr(data: dict) -> str` — pure; returns recognized text stripped of whitespace, or `""` on error/empty.
  - `app.ocr.ocr_image(image_bytes: bytes, api_key: str) -> str` — I/O; POSTs to OCR.space with the Japanese engine.

- [ ] **Step 1: Write the failing test** — `tests/test_ocr.py`

```python
from app.ocr import parse_ocr


def test_parse_ocr_success():
    data = {
        "IsErroredOnProcessing": False,
        "ParsedResults": [{"ParsedText": "今日\r\n"}],
    }
    assert parse_ocr(data) == "今日"


def test_parse_ocr_error_returns_empty():
    assert parse_ocr({"IsErroredOnProcessing": True, "ErrorMessage": ["bad"]}) == ""


def test_parse_ocr_no_results():
    assert parse_ocr({"IsErroredOnProcessing": False, "ParsedResults": []}) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ocr.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write `app/ocr.py`**

```python
import requests

API = "https://api.ocr.space/parse/image"


def parse_ocr(data: dict) -> str:
    if data.get("IsErroredOnProcessing"):
        return ""
    results = data.get("ParsedResults") or []
    if not results:
        return ""
    text = results[0].get("ParsedText", "") or ""
    return "".join(text.split())


def ocr_image(image_bytes: bytes, api_key: str) -> str:
    resp = requests.post(
        API,
        files={"file": ("image.png", image_bytes)},
        data={
            "apikey": api_key,
            "language": "jpn",
            "OCREngine": "1",
            "isOverlayRequired": "false",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return parse_ocr(resp.json())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ocr.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Manual live check (optional, needs a real key + a Japanese photo)**

Run:
```bash
python -c "import app.ocr, sys; print(repr(app.ocr.ocr_image(open('tests/fixtures/sample_jp.png','rb').read(), 'YOUR_KEY')))"
```
Expected: prints the recognized Japanese string. Skip if no key yet; the parse contract is covered by unit tests. If the Japanese engine misreads, note that `OCREngine=1` is the only free engine supporting `jpn`.

- [ ] **Step 6: Commit**

```bash
git add app/ocr.py tests/test_ocr.py
git commit -m "feat: OCR.space client for photo input"
```

---

### Task 6: Card builder (formatting + genanki .apkg)

**Files:**
- Create: `app/card.py`
- Test: `tests/test_card.py`

**Interfaces:**
- Consumes: `app.models.WordInfo`, `app.models.KanjiGloss`, `app.models.Example`, `app.config.MODEL_ID`.
- Produces:
  - `app.card.format_meaning(meanings: list[list[str]]) -> str` — numbered HTML lines: `"1. today; this day<br>2. ..."`.
  - `app.card.format_kanji_block(glosses: list[KanjiGloss]) -> str` — `"今 now<br>日 sun"`.
  - `app.card.deck_id_for(name: str) -> int` — deterministic genanki deck id from name.
  - `app.card.build_model() -> genanki.Model` — the fixed note type.
  - `app.card.build_apkg(word_info, glosses, example, image_path, sound_path, deck_name, out_path) -> str` — writes `.apkg` to `out_path` and returns it. `example`, `image_path`, `sound_path` may be `None`.

- [ ] **Step 1: Write the failing test** — `tests/test_card.py`

```python
import zipfile
from pathlib import Path

from app.card import format_meaning, format_kanji_block, deck_id_for, build_apkg
from app.models import WordInfo, KanjiGloss, Example


def test_format_meaning_numbers_senses():
    out = format_meaning([["today", "this day"], ["nowadays", "recently"]])
    assert out == "1. today; this day<br>2. nowadays; recently"


def test_format_kanji_block():
    out = format_kanji_block([KanjiGloss("今", "now"), KanjiGloss("日", "sun")])
    assert out == "今 now<br>日 sun"


def test_deck_id_is_stable_and_int():
    a = deck_id_for("Японский::Слова")
    b = deck_id_for("Японский::Слова")
    assert a == b and isinstance(a, int)
    assert a != deck_id_for("Other")


def test_build_apkg_without_media(tmp_path):
    wi = WordInfo(word="今日", reading="きょう", meanings=[["today"]])
    out = tmp_path / "deck.apkg"
    path = build_apkg(wi, [KanjiGloss("今", "now")], None, None, None,
                      "Test Deck", str(out))
    assert Path(path).exists()
    # .apkg is a zip containing an SQLite collection
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    assert "collection.anki2" in names


def test_build_apkg_with_media(tmp_path):
    img = tmp_path / "pic.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")          # minimal jpeg-ish bytes
    snd = tmp_path / "clip.mp3"
    snd.write_bytes(b"ID3")
    wi = WordInfo(word="今日", reading="きょう", meanings=[["today"]])
    ex = Example("今日はいい天気", "今日[きょう]はいい 天気[てんき]", "Nice weather today",
                 "pic.jpg", "clip.mp3", "castle_in_the_sky")
    out = tmp_path / "deck.apkg"
    build_apkg(wi, [KanjiGloss("今", "now")], ex, str(img), str(snd),
               "Test Deck", str(out))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    # media are stored as index files "0","1" plus a media manifest
    assert "media" in names
    assert "0" in names and "1" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_card.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write `app/card.py`**

```python
import hashlib

import genanki

from app.config import MODEL_ID
from app.models import Example, KanjiGloss, WordInfo


def format_meaning(meanings: list[list[str]]) -> str:
    lines = [f"{i}. {'; '.join(sense)}" for i, sense in enumerate(meanings, start=1)]
    return "<br>".join(lines)


def format_kanji_block(glosses: list[KanjiGloss]) -> str:
    return "<br>".join(f"{g.char} {g.meaning}" for g in glosses)


def deck_id_for(name: str) -> int:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
    return int(digest, 16) % (10 ** 10)


def build_model() -> genanki.Model:
    css = """
.card { font-family: sans-serif; font-size: 22px; text-align: center; color: #111; background: #fff; }
.word { font-size: 40px; font-weight: bold; margin: 12px 0; }
.section-title { font-weight: bold; margin-top: 20px; }
.sentence { margin: 14px 0; }
img { max-width: 90%; margin-top: 16px; }
"""
    front = '<div class="word">{{Word}}</div>\n<div class="sentence">{{kanji:SentenceFurigana}}</div>'
    back = (
        "{{FrontSide}}\n<hr>\n"
        '<div class="section-title">Meaning</div>\n<div>{{Meaning}}</div>\n'
        '<div class="section-title">Kanji used</div>\n<div>{{KanjiUsed}}</div>\n'
        '<div class="section-title">Example</div>\n'
        '<div class="sentence">{{furigana:SentenceFurigana}}</div>\n'
        "<div>{{Translation}}</div>\n"
        "<div>{{Audio}}</div>\n"
        "<div>{{Image}}</div>"
    )
    return genanki.Model(
        MODEL_ID,
        "Kanji Anki Bot",
        fields=[
            {"name": "Word"},
            {"name": "Reading"},
            {"name": "Meaning"},
            {"name": "KanjiUsed"},
            {"name": "SentenceFurigana"},
            {"name": "Translation"},
            {"name": "Audio"},
            {"name": "Image"},
        ],
        templates=[{"name": "Card 1", "qfmt": front, "afmt": back}],
        css=css,
    )


def build_apkg(
    word_info: WordInfo,
    glosses: list[KanjiGloss],
    example: Example | None,
    image_path: str | None,
    sound_path: str | None,
    deck_name: str,
    out_path: str,
) -> str:
    import os

    sentence = example.sentence_furigana if example else ""
    translation = example.translation if example else ""
    audio_field = ""
    image_field = ""
    media_files: list[str] = []

    if example and sound_path:
        audio_field = f"[sound:{os.path.basename(sound_path)}]"
        media_files.append(sound_path)
    if example and image_path:
        image_field = f'<img src="{os.path.basename(image_path)}">'
        media_files.append(image_path)

    note = genanki.Note(
        model=build_model(),
        fields=[
            word_info.word,
            word_info.reading,
            format_meaning(word_info.meanings),
            format_kanji_block(glosses),
            sentence,
            translation,
            audio_field,
            image_field,
        ],
    )
    deck = genanki.Deck(deck_id_for(deck_name), deck_name)
    deck.add_note(note)
    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(out_path)
    return out_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_card.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/card.py tests/test_card.py
git commit -m "feat: card formatting and genanki .apkg builder"
```

---

### Task 7: Orchestration + Telegram handlers

**Files:**
- Create: `app/lookup.py`, `app/handlers.py`
- Test: `tests/test_lookup.py`, `tests/test_handlers.py`

**Interfaces:**
- Consumes: all clients (`jisho`, `kanji`, `immersionkit`), `card`, `config`.
- Produces:
  - `app.lookup.CardData` dataclass: `word_info: WordInfo`, `glosses: list[KanjiGloss]`, `examples: list[Example]`.
  - `app.lookup.gather(word: str) -> CardData | None` — I/O; runs the three fetchers; returns `None` if Jisho has no entry.
  - `app.handlers.preview_text(cd: CardData, index: int) -> str` — pure; Russian preview of word/reading/meaning + the example at `index` (or a "no example" note).
  - `app.handlers.deck_keyboard(deck_names: list[str]) -> InlineKeyboardMarkup` — pure.
  - `app.handlers.register(application, settings)` — wires handlers onto a PTB `Application`; each handler first checks `update.effective_user.id == settings.owner_id`.

- [ ] **Step 1: Write the failing test** — `tests/test_lookup.py`

```python
import app.lookup as lookup
from app.models import WordInfo, KanjiGloss, Example


def test_gather_returns_none_when_jisho_empty(monkeypatch):
    monkeypatch.setattr(lookup.jisho, "fetch_word", lambda w: None)
    monkeypatch.setattr(lookup.kanji, "fetch_breakdown", lambda w: [])
    monkeypatch.setattr(lookup.immersionkit, "fetch_examples", lambda w: [])
    assert lookup.gather("今日") is None


def test_gather_assembles(monkeypatch):
    wi = WordInfo("今日", "きょう", [["today"]])
    ex = [Example("s", "s[k]", "t", "i.jpg", "a.mp3", "castle_in_the_sky")]
    monkeypatch.setattr(lookup.jisho, "fetch_word", lambda w: wi)
    monkeypatch.setattr(lookup.kanji, "fetch_breakdown", lambda w: [KanjiGloss("今", "now")])
    monkeypatch.setattr(lookup.immersionkit, "fetch_examples", lambda w: ex)
    cd = lookup.gather("今日")
    assert cd.word_info is wi
    assert cd.glosses[0].char == "今"
    assert cd.examples == ex
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lookup.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write `app/lookup.py`**

```python
from dataclasses import dataclass

from app import immersionkit, jisho, kanji
from app.models import Example, KanjiGloss, WordInfo


@dataclass
class CardData:
    word_info: WordInfo
    glosses: list[KanjiGloss]
    examples: list[Example]


def gather(word: str) -> CardData | None:
    word_info = jisho.fetch_word(word)
    if word_info is None:
        return None
    glosses = kanji.fetch_breakdown(word)
    try:
        examples = immersionkit.fetch_examples(word)
    except Exception:
        examples = []
    return CardData(word_info=word_info, glosses=glosses, examples=examples)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_lookup.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Write the failing test** — `tests/test_handlers.py`

```python
from app.handlers import preview_text, deck_keyboard
from app.lookup import CardData
from app.models import WordInfo, KanjiGloss, Example


def _cd(with_example=True):
    ex = [Example("今日はいい天気", "今日[きょう]はいい 天気[てんき]",
                  "Nice weather", "i.jpg", "a.mp3", "castle_in_the_sky")] if with_example else []
    return CardData(WordInfo("今日", "きょう", [["today", "this day"]]),
                    [KanjiGloss("今", "now"), KanjiGloss("日", "sun")], ex)


def test_preview_text_includes_word_and_example():
    txt = preview_text(_cd(), 0)
    assert "今日" in txt
    assert "きょう" in txt
    assert "today" in txt
    assert "天気" in txt or "Nice weather" in txt


def test_preview_text_no_example():
    txt = preview_text(_cd(with_example=False), 0)
    assert "без примера" in txt.lower() or "нет примера" in txt.lower()


def test_deck_keyboard_has_button_per_deck():
    kb = deck_keyboard(["A", "B"])
    flat = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "A" in flat and "B" in flat
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/test_handlers.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 7: Write `app/handlers.py`**

```python
import os
import tempfile

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app import card, immersionkit, lookup, ocr
from app.config import Settings, load_deck_map


def preview_text(cd: lookup.CardData, index: int) -> str:
    wi = cd.word_info
    meaning = "; ".join(wi.meanings[0]) if wi.meanings else "—"
    lines = [f"📝 {wi.word} ({wi.reading}) — {meaning}"]
    if cd.examples:
        ex = cd.examples[index % len(cd.examples)]
        lines.append("")
        lines.append(f"例 {ex.sentence}")
        lines.append(f"— {ex.translation}")
        lines.append(f"({index % len(cd.examples) + 1}/{len(cd.examples)})")
    else:
        lines.append("")
        lines.append("⚠️ Карточка будет собрана без примера (пример не найден).")
    return "\n".join(lines)


def deck_keyboard(deck_names: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(name, callback_data=f"deck:{i}")]
            for i, name in enumerate(deck_names)]
    return InlineKeyboardMarkup(rows)


def _preview_keyboard(has_examples: bool) -> InlineKeyboardMarkup:
    row = []
    if has_examples:
        row.append(InlineKeyboardButton("🔀 Другой пример", callback_data="next"))
    row.append(InlineKeyboardButton("✅ Выбрать колоду", callback_data="choose"))
    return InlineKeyboardMarkup([row])


def _download(url: str, suffix: str) -> str | None:
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
    except requests.RequestException:
        return None
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(r.content)
    return path


def register(application: Application, settings: Settings) -> None:
    deck_map = load_deck_map()

    def owns(update: Update) -> bool:
        return update.effective_user and update.effective_user.id == settings.owner_id

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not owns(update):
            return
        await update.message.reply_text(
            "Пришли кандзи текстом или фото — соберу карточку Anki.")

    async def _run_lookup(update, ctx, word):
        word = word.strip()
        await update.message.reply_text(f"🔎 Ищу «{word}»…")
        cd = await _to_thread(lookup.gather, word)
        if cd is None:
            await update.message.reply_text("Не нашёл такое слово в Jisho. Проверь написание.")
            return
        ctx.user_data["cd"] = cd
        ctx.user_data["index"] = 0
        await update.message.reply_text(
            preview_text(cd, 0), reply_markup=_preview_keyboard(bool(cd.examples)))

    async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not owns(update):
            return
        if ctx.user_data.get("awaiting_custom_deck"):
            ctx.user_data["awaiting_custom_deck"] = False
            await _build_and_send(update, ctx, update.message.text.strip())
            return
        await _run_lookup(update, ctx, update.message.text)

    async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not owns(update):
            return
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        buf = await tg_file.download_as_bytearray()
        await update.message.reply_text("🖼 Распознаю…")
        word = await _to_thread(ocr.ocr_image, bytes(buf), settings.ocr_api_key)
        if not word:
            await update.message.reply_text("Не смог распознать. Пришли слово текстом.")
            return
        await _run_lookup(update, ctx, word)

    async def on_next(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        cd = ctx.user_data.get("cd")
        if not cd:
            return
        ctx.user_data["index"] = ctx.user_data.get("index", 0) + 1
        await q.edit_message_text(
            preview_text(cd, ctx.user_data["index"]),
            reply_markup=_preview_keyboard(bool(cd.examples)))

    async def on_choose(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        rows = deck_keyboard(settings.deck_names).inline_keyboard
        rows = list(rows) + [[InlineKeyboardButton("✏️ Своя колода", callback_data="custom")]]
        await q.edit_message_text("В какую колоду добавить?",
                                  reply_markup=InlineKeyboardMarkup(rows))

    async def on_deck(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        idx = int(q.data.split(":", 1)[1])
        await _build_and_send(update, ctx, settings.deck_names[idx], via_query=True)

    async def on_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        ctx.user_data["awaiting_custom_deck"] = True
        await q.edit_message_text("Напиши название колоды сообщением.")

    async def _build_and_send(update, ctx, deck_name, via_query=False):
        cd = ctx.user_data.get("cd")
        chat = update.effective_chat
        if not cd:
            await chat.send_message("Сессия истекла, пришли слово заново.")
            return
        index = ctx.user_data.get("index", 0)
        example = cd.examples[index % len(cd.examples)] if cd.examples else None
        image_path = sound_path = None
        if example:
            img_url, snd_url = immersionkit.media_urls(example, deck_map)
            if img_url:
                image_path = await _to_thread(_download, img_url, ".jpg")
            if snd_url:
                sound_path = await _to_thread(_download, snd_url, ".mp3")
        out = tempfile.mktemp(suffix=".apkg")
        await _to_thread(card.build_apkg, cd.word_info, cd.glosses, example,
                         image_path, sound_path, deck_name, out)
        with open(out, "rb") as f:
            await chat.send_document(f, filename=f"{cd.word_info.word}.apkg",
                                     caption=f"Готово → «{deck_name}». Открой в AnkiMobile.")

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, on_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    application.add_handler(CallbackQueryHandler(on_next, pattern="^next$"))
    application.add_handler(CallbackQueryHandler(on_choose, pattern="^choose$"))
    application.add_handler(CallbackQueryHandler(on_custom, pattern="^custom$"))
    application.add_handler(CallbackQueryHandler(on_deck, pattern="^deck:"))


async def _to_thread(func, *args):
    import asyncio
    return await asyncio.to_thread(func, *args)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/test_handlers.py tests/test_lookup.py -v`
Expected: PASS (5 passed).

- [ ] **Step 9: Commit**

```bash
git add app/lookup.py app/handlers.py tests/test_lookup.py tests/test_handlers.py
git commit -m "feat: lookup orchestration and Telegram handlers"
```

---

### Task 8: Entry point, Docker, and Hugging Face deployment guide

**Files:**
- Create: `app/main.py`, `Dockerfile`, `README.md`

**Interfaces:**
- Consumes: `app.config.settings`, `app.handlers.register`.
- Produces: a runnable module `python -m app.main` that starts a health server on port 7860 and runs PTB polling.

- [ ] **Step 1: Write `app/main.py`**

```python
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram.ext import ApplicationBuilder

from app.config import settings
from app.handlers import register


class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def _start_health(port: int = 7860) -> None:
    server = HTTPServer(("0.0.0.0", port), _Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def main() -> None:
    cfg = settings()
    if not cfg.bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    _start_health()
    application = ApplicationBuilder().token(cfg.bot_token).build()
    register(application, cfg)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the process boots (health server responds; bot token rejected cleanly)**

Run:
```bash
TELEGRAM_BOT_TOKEN=dummy OCR_SPACE_API_KEY=x ALLOWED_TELEGRAM_USER_ID=1 DECK_NAMES=Default \
  python -c "import app.main as m; m._start_health(7860); import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:7860').read())"
```
Expected: prints `b'ok'`.

- [ ] **Step 3: Run the whole test suite**

Run: `python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 4: Write `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

EXPOSE 7860
CMD ["python", "-m", "app.main"]
```

- [ ] **Step 5: Write `README.md` (deployment guide)**

````markdown
# Kanji → Anki Telegram Bot

Send the bot a Japanese word (text or photo); it replies with a ready-to-import
Anki `.apkg` card (meaning, kanji breakdown, example sentence with audio + image),
and lets you choose the target deck. Open the file in AnkiMobile to import.

## One-time setup (~15 min)

### 1. Create the Telegram bot
1. In Telegram, open **@BotFather** → `/newbot` → follow prompts.
2. Copy the **bot token** it gives you.

### 2. Find your Telegram user id
Message **@userinfobot** in Telegram; it replies with your numeric **Id**.
(The bot only answers this id, so nobody else can use your quota.)

### 3. Get a free OCR key
Register at https://ocr.space/ocrapi → you get a free API key by email.

### 4. Deploy to Hugging Face Spaces (free, no card)
1. Create a free account at https://huggingface.co.
2. **New Space** → SDK: **Docker** → Blank → name it (e.g. `kanji-anki-bot`).
3. Upload this project's files (or `git push` to the Space repo).
4. In the Space → **Settings → Variables and secrets**, add secrets:
   - `TELEGRAM_BOT_TOKEN` = your bot token
   - `OCR_SPACE_API_KEY` = your OCR key
   - `ALLOWED_TELEGRAM_USER_ID` = your numeric id
   - `DECK_NAMES` = comma-separated deck names, e.g. `Японский::Слова,Японский::Кандзи`
5. The Space builds and starts automatically. When it says **Running**, message
   your bot `/start`.

## Usage
- Send a word as **text** (`今日`) or a **photo**.
- Tap **🔀 Другой пример** to cycle example sentences (shortest first).
- Tap **✅ Выбрать колоду**, pick a deck (or **✏️ Своя колода** to type one).
- The bot sends a `.apkg`; open it in **AnkiMobile → Import**.

## Notes
- On the free tier the Space may sleep after long inactivity; the first message
  after a nap can take ~30 s while it wakes, then works normally.
- The kanji gloss comes from kanjiapi.dev and may differ slightly from jpdb's
  hand-picked wording.
````

- [ ] **Step 6: Local Docker smoke test (optional)**

Run:
```bash
docker build -t kanji-anki-bot . && \
docker run --rm -e TELEGRAM_BOT_TOKEN=dummy -e OCR_SPACE_API_KEY=x \
  -e ALLOWED_TELEGRAM_USER_ID=1 -e DECK_NAMES=Default -p 7860:7860 kanji-anki-bot &
sleep 8 && curl -s localhost:7860 && echo
```
Expected: prints `ok` (the health endpoint). The bot will log a Telegram auth error for the dummy token — that is expected; it confirms wiring. Stop the container afterward.

- [ ] **Step 7: Commit**

```bash
git add app/main.py Dockerfile README.md
git commit -m "feat: entry point, Dockerfile, and Hugging Face deployment guide"
```

---

## Self-Review

**Spec coverage:**
- Text input → Task 7 (`on_text`). ✅
- Photo input + OCR → Task 5 + Task 7 (`on_photo`). ✅
- Meaning + Kanji from Jisho/kanjiapi → Tasks 2, 3. ✅ (design-approved substitution for jpdb)
- Example + audio + image from ImmersionKit → Task 4 + media download in Task 7. ✅
- Card template matching screenshot (Meaning / Kanji used / Example / audio / image, furigana) → Task 6. ✅
- Deck selection via buttons + custom name → Task 7 (`on_choose`, `on_deck`, `on_custom`). ✅
- Deliver `.apkg` to chat → Task 7 (`_build_and_send`). ✅
- Free, 24/7, no MacBook (HF Docker Space) → Task 8. ✅
- Error handling: no Jisho entry (Task 7 `_run_lookup`), no example (Task 6/7 handle `example=None`), OCR fail (Task 7 `on_photo`), media download fail (Task 7 `_download` returns None → card built without that media). ✅
- Owner-only access → Task 7 (`owns`). ✅ (added for OCR-quota protection)

**Placeholder scan:** No TODO/TBD; every code step contains complete code; every test step has real assertions.

**Type consistency:** `WordInfo`, `KanjiGloss`, `Example` defined in Task 2 and used with the same field names throughout. `media_urls(ex, deck_map)` signature consistent (Task 4 defn, Task 7 call). `build_apkg(...)` signature consistent (Task 6 defn, Task 7 call). `gather` / `CardData` consistent (Task 7 defn + tests). `_to_thread` defined and used in `handlers.py`.

**Note on `{{kanji:...}}`/`{{furigana:...}}`:** these are Anki's built-in field filters; they render on import in Anki/AnkiMobile. genanki stores the template verbatim, so no extra handling is needed.
