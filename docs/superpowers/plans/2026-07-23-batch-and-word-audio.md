# Batch Mode + Word Audio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add (1) a batch mode — collect several words and export them as one `.apkg` into one chosen deck — and (2) word-pronunciation audio on the card front (native JapanesePod101, synthetic TTS fallback).

**Architecture:** A new `app/word_audio.py` fetches the word's pronunciation (native → placeholder-detect → TTS). `app/card.py` gains a 9th `WordAudio` field + a front play control and becomes a **batch** builder (`build_apkg(list[(CardSpec, CardMedia)], deck, out)`). `app/handlers.py` accumulates confirmed words as `CardSpec`s in `user_data["batch"]`; a **➕ Добавить в партию** button appends, a **📦 Выгрузить** button picks the deck once and builds/sends the whole batch.

**Tech Stack:** Python (3.9 local test venv / 3.11 deploy), python-telegram-bot 21.6, genanki 0.13.1, requests, pytest.

## Global Constraints

- Local tests run on Python 3.9 via `.venv/bin/python -m pytest`; deploy image is python:3.11-slim. Every new/edited `app/*.py` keeps `from __future__ import annotations` as its first line.
- **New note type:** because the note type gains a field, bump it to a NEW identity so Anki does not collide with the already-imported 8-field type: `MODEL_ID = 1608310002` and model name **`"Kanji Anki Bot 2"`** (both set in this plan). Old cards keep the old type; new cards use the new one. Do not reuse the old id `1608310001` for the new 9-field model.
- Requests to hosts that block datacenter IPs use browser headers (as ImmersionKit already does). All external fetches degrade gracefully (return `None` / skip media, never crash the handler).
- jpod101 "not found" placeholder mp3 = **md5 `7e2c2f954ef6051373ba916f000168dc`** (52288 bytes); committed at `tests/fixtures/jpod_placeholder.mp3`.
- Word-audio play control goes on the **front**, directly under the word.
- After merge to `main`: push, then in Render click **Manual Deploy → Deploy latest commit** (public-repo connection does not auto-deploy).

---

## File Structure

```
app/
  word_audio.py     # NEW: word pronunciation (jpod101 native + TTS fallback)
  models.py         # + CardSpec, CardMedia dataclasses
  card.py           # + WordAudio field/template; batch build_apkg
  handlers.py       # batch state + ➕ add / 📦 export flow, word-audio download
  config.py         # MODEL_ID bumped to new note-type id
tests/
  test_word_audio.py    # NEW
  test_card.py          # updated for new signature + WordAudio
  test_handlers.py      # + add/export keyboard tests
  fixtures/jpod_placeholder.mp3   # committed
```

---

### Task 1: Word audio module (`app/word_audio.py`)

**Files:**
- Create: `app/word_audio.py`
- Test: `tests/test_word_audio.py`
- Fixture (already committed): `tests/fixtures/jpod_placeholder.mp3`

**Interfaces:**
- Produces:
  - `app.word_audio.is_placeholder(content: bytes) -> bool` — pure; true iff `content` is the jpod101 "not found" placeholder (md5 match).
  - `app.word_audio.fetch_word_audio(word: str, reading: str) -> bytes | None` — I/O; jpod101 native → placeholder → Google TTS fallback → `None` on total failure.

- [ ] **Step 1: Write the failing test** — `tests/test_word_audio.py`

```python
from pathlib import Path

import app.word_audio as wa

FIX = Path(__file__).parent / "fixtures"


class _Resp:
    def __init__(self, content=b"", status=200):
        self.content = content
        self.status_code = status


def test_is_placeholder_true_for_fixture():
    data = (FIX / "jpod_placeholder.mp3").read_bytes()
    assert wa.is_placeholder(data) is True


def test_is_placeholder_false_for_other_bytes():
    assert wa.is_placeholder(b"real audio bytes") is False


def test_fetch_returns_native_when_present(monkeypatch):
    def fake_get(url, **kw):
        assert "languagepod101" in url
        return _Resp(b"NATIVE-AUDIO")
    monkeypatch.setattr(wa.requests, "get", fake_get)
    assert wa.fetch_word_audio("今日", "きょう") == b"NATIVE-AUDIO"


def test_fetch_falls_back_to_tts_on_placeholder(monkeypatch):
    placeholder = (FIX / "jpod_placeholder.mp3").read_bytes()

    def fake_get(url, **kw):
        if "languagepod101" in url:
            return _Resp(placeholder)          # native missing → placeholder
        return _Resp(b"TTS-AUDIO")             # google tts
    monkeypatch.setattr(wa.requests, "get", fake_get)
    assert wa.fetch_word_audio("峠", "とうげ") == b"TTS-AUDIO"


def test_fetch_returns_none_when_both_fail(monkeypatch):
    def fake_get(url, **kw):
        raise wa.requests.RequestException("boom")
    monkeypatch.setattr(wa.requests, "get", fake_get)
    assert wa.fetch_word_audio("今日", "きょう") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_word_audio.py -v`
Expected: FAIL (ModuleNotFoundError: app.word_audio).

- [ ] **Step 3: Write `app/word_audio.py`**

```python
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
            headers=_HEADERS,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_word_audio.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/word_audio.py tests/test_word_audio.py tests/fixtures/jpod_placeholder.mp3
git commit -m "feat: word pronunciation audio (JapanesePod101 + TTS fallback)"
```

---

### Task 2: Model fields + batch card builder

**Files:**
- Modify: `app/models.py` (add `CardSpec`, `CardMedia`)
- Modify: `app/config.py` (bump `MODEL_ID`)
- Modify: `app/card.py` (WordAudio field/template; batch `build_apkg`)
- Modify: `tests/test_card.py` (new signature + WordAudio)

**Interfaces:**
- Consumes: `app.models.WordInfo`, `KanjiGloss`, `Example`; `app.config.MODEL_ID`.
- Produces:
  - `app.models.CardSpec(word_info: WordInfo, glosses: list[KanjiGloss], example: Example | None)`
  - `app.models.CardMedia(image_path: str | None = None, sound_path: str | None = None, word_audio_path: str | None = None)`
  - `app.card.build_apkg(items: list[tuple[CardSpec, CardMedia]], deck_name: str, out_path: str) -> str`
  - `app.card.build_model()` now has 9 fields (adds `WordAudio`) and model name `"Kanji Anki Bot 2"`.

- [ ] **Step 1: Bump `MODEL_ID` in `app/config.py`**

Change the line `MODEL_ID = 1608310001` to:

```python
MODEL_ID = 1608310002
```

- [ ] **Step 2: Add dataclasses to `app/models.py`**

Append to `app/models.py` (keep existing dataclasses unchanged):

```python
@dataclass
class CardSpec:
    word_info: WordInfo
    glosses: list[KanjiGloss]
    example: Example | None


@dataclass
class CardMedia:
    image_path: str | None = None
    sound_path: str | None = None
    word_audio_path: str | None = None
```

- [ ] **Step 3: Write the failing test** — replace the body of `tests/test_card.py` with:

```python
import zipfile
from pathlib import Path

from app.card import format_meaning, format_kanji_block, deck_id_for, build_apkg, build_model
from app.models import WordInfo, KanjiGloss, Example, CardSpec, CardMedia


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


def test_model_has_word_audio_field_and_front_control():
    model = build_model()
    field_names = [f["name"] for f in model.fields]
    assert field_names == [
        "Word", "Reading", "Meaning", "KanjiUsed", "SentenceFurigana",
        "Translation", "Audio", "Image", "WordAudio",
    ]
    front = model.templates[0]["qfmt"]
    assert "{{WordAudio}}" in front          # word audio plays on the front


def test_build_apkg_single_card_no_media(tmp_path):
    spec = CardSpec(WordInfo("今日", "きょう", [["today"]]), [KanjiGloss("今", "now")], None)
    out = tmp_path / "deck.apkg"
    path = build_apkg([(spec, CardMedia())], "Test Deck", str(out))
    assert Path(path).exists()
    with zipfile.ZipFile(path) as z:
        assert "collection.anki2" in z.namelist()


def test_build_apkg_batch_with_word_audio_and_example(tmp_path):
    wav = tmp_path / "word.mp3"; wav.write_bytes(b"ID3word")
    img = tmp_path / "pic.jpg"; img.write_bytes(b"\xff\xd8\xff\xd9")
    snd = tmp_path / "clip.mp3"; snd.write_bytes(b"ID3clip")
    ex = Example("今日はいい天気", "今日[きょう]はいい 天気[てんき]", "Nice weather",
                 "pic.jpg", "clip.mp3", "castle_in_the_sky")
    spec1 = CardSpec(WordInfo("今日", "きょう", [["today"]]), [KanjiGloss("今", "now")], ex)
    media1 = CardMedia(image_path=str(img), sound_path=str(snd), word_audio_path=str(wav))
    wav2 = tmp_path / "word2.mp3"; wav2.write_bytes(b"ID3word2")
    spec2 = CardSpec(WordInfo("子供", "こども", [["child"]]), [KanjiGloss("子", "child")], None)
    media2 = CardMedia(word_audio_path=str(wav2))

    out = tmp_path / "batch.apkg"
    build_apkg([(spec1, media1), (spec2, media2)], "Test Deck", str(out))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    # media manifest + 4 media files (img, clip, word, word2) stored as "0".."3"
    assert "media" in names
    assert {"0", "1", "2", "3"}.issubset(set(names))
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_card.py -v`
Expected: FAIL (ImportError: cannot import name `CardSpec` / `build_apkg` signature).

- [ ] **Step 5: Rewrite `app/card.py`**

```python
from __future__ import annotations

import hashlib
import os

import genanki

from app.config import MODEL_ID
from app.models import CardMedia, CardSpec, KanjiGloss


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
    front = (
        '<div class="word">{{Word}}</div>\n'
        "<div>{{WordAudio}}</div>\n"
        '<div class="sentence">{{kanji:SentenceFurigana}}</div>'
    )
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
        "Kanji Anki Bot 2",
        fields=[
            {"name": "Word"},
            {"name": "Reading"},
            {"name": "Meaning"},
            {"name": "KanjiUsed"},
            {"name": "SentenceFurigana"},
            {"name": "Translation"},
            {"name": "Audio"},
            {"name": "Image"},
            {"name": "WordAudio"},
        ],
        templates=[{"name": "Card 1", "qfmt": front, "afmt": back}],
        css=css,
    )


def _build_note(model: genanki.Model, spec: CardSpec, media: CardMedia):
    example = spec.example
    sentence = example.sentence_furigana if example else ""
    translation = example.translation if example else ""
    audio_field = ""
    image_field = ""
    word_audio_field = ""
    media_files: list[str] = []

    if example and media.sound_path:
        audio_field = f"[sound:{os.path.basename(media.sound_path)}]"
        media_files.append(media.sound_path)
    if example and media.image_path:
        image_field = f'<img src="{os.path.basename(media.image_path)}">'
        media_files.append(media.image_path)
    if media.word_audio_path:
        word_audio_field = f"[sound:{os.path.basename(media.word_audio_path)}]"
        media_files.append(media.word_audio_path)

    note = genanki.Note(
        model=model,
        fields=[
            spec.word_info.word,
            spec.word_info.reading,
            format_meaning(spec.word_info.meanings),
            format_kanji_block(spec.glosses),
            sentence,
            translation,
            audio_field,
            image_field,
            word_audio_field,
        ],
    )
    return note, media_files


def build_apkg(items: list[tuple[CardSpec, CardMedia]], deck_name: str, out_path: str) -> str:
    model = build_model()
    deck = genanki.Deck(deck_id_for(deck_name), deck_name)
    all_media: list[str] = []
    for spec, media in items:
        note, media_files = _build_note(model, spec, media)
        deck.add_note(note)
        all_media.extend(media_files)
    package = genanki.Package(deck)
    package.media_files = all_media
    package.write_to_file(out_path)
    return out_path
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_card.py -v`
Expected: PASS (6 passed).

- [ ] **Step 7: Run the full suite (catches handler breakage before Task 3)**

Run: `.venv/bin/python -m pytest -q`
Expected: `tests/test_handlers.py` may FAIL to import (it still calls the old `card.build_apkg`); everything else passes. That is expected and fixed in Task 3. Confirm ONLY handler-related failures, then proceed.

- [ ] **Step 8: Commit**

```bash
git add app/config.py app/models.py app/card.py tests/test_card.py
git commit -m "feat: WordAudio field + batch .apkg builder (new note type)"
```

---

### Task 3: Batch flow in handlers

**Files:**
- Modify: `app/handlers.py`
- Modify: `tests/test_handlers.py`

**Interfaces:**
- Consumes: `app.card.build_apkg(items, deck, out)`, `app.models.CardSpec`, `app.models.CardMedia`, `app.word_audio.fetch_word_audio`, `app.immersionkit.media_urls`, existing `lookup.gather`.
- Produces (module-level, testable):
  - `app.handlers._preview_keyboard(multiple_examples: bool) -> InlineKeyboardMarkup` — now offers **➕ Добавить в партию** (`callback_data="add"`) plus 🔀 when `multiple_examples`.
  - `app.handlers.export_button(count: int) -> InlineKeyboardMarkup` — one button "📦 Выгрузить ({count})" (`callback_data="export"`).

- [ ] **Step 1: Write the failing test** — replace the body of `tests/test_handlers.py` with:

```python
from app.handlers import preview_text, deck_keyboard, _preview_keyboard, export_button
from app.lookup import CardData
from app.models import WordInfo, KanjiGloss, Example


def _cd(with_example=True):
    ex = [Example("今日はいい天気", "今日[きょう]はいい 天気[てんき]",
                  "Nice weather", "i.jpg", "a.mp3", "castle_in_the_sky")] if with_example else []
    return CardData(WordInfo("今日", "きょう", [["today", "this day"]]),
                    [KanjiGloss("今", "now"), KanjiGloss("日", "sun")], ex)


def test_preview_text_includes_word_and_example():
    txt = preview_text(_cd(), 0)
    assert "今日" in txt and "きょう" in txt and "today" in txt
    assert "天気" in txt or "Nice weather" in txt


def test_preview_text_no_example():
    txt = preview_text(_cd(with_example=False), 0)
    assert "без примера" in txt.lower() or "нет примера" in txt.lower()


def test_deck_keyboard_has_button_per_deck():
    kb = deck_keyboard(["A", "B"])
    flat = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "A" in flat and "B" in flat


def test_preview_keyboard_offers_add_to_batch():
    kb = _preview_keyboard(multiple_examples=True)
    datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "add" in datas          # ➕ Добавить в партию
    assert "next" in datas         # 🔀 shown when multiple examples


def test_preview_keyboard_single_example_has_no_shuffle():
    kb = _preview_keyboard(multiple_examples=False)
    datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "add" in datas
    assert "next" not in datas


def test_export_button_shows_count_and_callback():
    kb = export_button(3)
    btn = kb.inline_keyboard[0][0]
    assert "3" in btn.text
    assert btn.callback_data == "export"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_handlers.py -v`
Expected: FAIL (ImportError: cannot import name `export_button`).

- [ ] **Step 3: Rewrite `app/handlers.py`**

```python
from __future__ import annotations

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

from app import card, immersionkit, lookup, ocr, word_audio
from app.config import Settings, load_deck_map
from app.models import CardMedia, CardSpec


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


def _preview_keyboard(multiple_examples: bool) -> InlineKeyboardMarkup:
    row = []
    if multiple_examples:
        row.append(InlineKeyboardButton("🔀 Другой пример", callback_data="next"))
    row.append(InlineKeyboardButton("➕ Добавить в партию", callback_data="add"))
    return InlineKeyboardMarkup([row])


def export_button(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"📦 Выгрузить ({count})", callback_data="export")]]
    )


def _download(url: str, suffix: str) -> str | None:
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
    except requests.RequestException:
        return None
    return _write_temp(r.content, suffix)


def _write_temp(content: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


def register(application: Application, settings: Settings) -> None:
    deck_map = load_deck_map()

    def owns(update: Update) -> bool:
        return bool(update.effective_user and update.effective_user.id == settings.owner_id)

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not owns(update):
            return
        await update.message.reply_text(
            "Пришли кандзи текстом или фото. Добавляй слова в партию и выгружай "
            "их одним файлом в Anki.")

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
            preview_text(cd, 0), reply_markup=_preview_keyboard(len(cd.examples) > 1))

    async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not owns(update):
            return
        if ctx.user_data.get("awaiting_custom_deck"):
            ctx.user_data["awaiting_custom_deck"] = False
            await _export_batch(update, ctx, update.message.text.strip())
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
        if not owns(update):
            return
        cd = ctx.user_data.get("cd")
        if not cd:
            return
        ctx.user_data["index"] = ctx.user_data.get("index", 0) + 1
        await q.edit_message_text(
            preview_text(cd, ctx.user_data["index"]),
            reply_markup=_preview_keyboard(len(cd.examples) > 1))

    async def on_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        if not owns(update):
            return
        cd = ctx.user_data.get("cd")
        if not cd:
            return
        index = ctx.user_data.get("index", 0)
        example = cd.examples[index % len(cd.examples)] if cd.examples else None
        spec = CardSpec(word_info=cd.word_info, glosses=cd.glosses, example=example)
        batch = ctx.user_data.setdefault("batch", [])
        batch.append(spec)
        await q.edit_message_text(
            f"✅ Добавлено: {cd.word_info.word} (в партии: {len(batch)})",
            reply_markup=export_button(len(batch)))

    async def on_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        if not owns(update):
            return
        batch = ctx.user_data.get("batch") or []
        if not batch:
            await q.edit_message_text("Партия пуста. Пришли слова и добавь их в партию.")
            return
        rows = list(deck_keyboard(settings.deck_names).inline_keyboard)
        rows.append([InlineKeyboardButton("✏️ Своя колода", callback_data="custom")])
        await q.edit_message_text(
            f"В какую колоду выгрузить {len(batch)} карт.?",
            reply_markup=InlineKeyboardMarkup(rows))

    async def on_deck(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        if not owns(update):
            return
        idx = int(q.data.split(":", 1)[1])
        await _export_batch(update, ctx, settings.deck_names[idx])

    async def on_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        if not owns(update):
            return
        ctx.user_data["awaiting_custom_deck"] = True
        await q.edit_message_text("Напиши название колоды сообщением.")

    async def _export_batch(update, ctx, deck_name):
        chat = update.effective_chat
        batch = ctx.user_data.get("batch") or []
        if not batch:
            await chat.send_message("Партия пуста.")
            return
        await chat.send_message(f"⏳ Собираю {len(batch)} карт.…")
        temp_paths: list[str] = []
        out = None
        try:
            items: list[tuple[CardSpec, CardMedia]] = []
            for spec in batch:
                media = CardMedia()
                if spec.example:
                    img_url, snd_url = immersionkit.media_urls(spec.example, deck_map)
                    if img_url:
                        media.image_path = await _to_thread(_download, img_url, ".jpg")
                    if snd_url:
                        media.sound_path = await _to_thread(_download, snd_url, ".mp3")
                audio = await _to_thread(
                    word_audio.fetch_word_audio, spec.word_info.word, spec.word_info.reading)
                if audio:
                    media.word_audio_path = _write_temp(audio, ".mp3")
                for p in (media.image_path, media.sound_path, media.word_audio_path):
                    if p:
                        temp_paths.append(p)
                items.append((spec, media))
            fd, out = tempfile.mkstemp(suffix=".apkg")
            os.close(fd)
            await _to_thread(card.build_apkg, items, deck_name, out)
            first = batch[0].word_info.word
            fname = f"{first}_{len(batch)}.apkg" if len(batch) > 1 else f"{first}.apkg"
            with open(out, "rb") as f:
                await chat.send_document(
                    f, filename=fname,
                    caption=f"Готово: {len(batch)} карт. → «{deck_name}». Открой в AnkiMobile.")
            ctx.user_data["batch"] = []
        finally:
            for p in temp_paths + ([out] if out else []):
                try:
                    os.remove(p)
                except OSError:
                    pass

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, on_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    application.add_handler(CallbackQueryHandler(on_next, pattern="^next$"))
    application.add_handler(CallbackQueryHandler(on_add, pattern="^add$"))
    application.add_handler(CallbackQueryHandler(on_export, pattern="^export$"))
    application.add_handler(CallbackQueryHandler(on_custom, pattern="^custom$"))
    application.add_handler(CallbackQueryHandler(on_deck, pattern="^deck:"))


async def _to_thread(func, *args):
    import asyncio
    return await asyncio.to_thread(func, *args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_handlers.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (word_audio 5 + card 6 + handlers 6 + the earlier suites).

- [ ] **Step 6: Commit**

```bash
git add app/handlers.py tests/test_handlers.py
git commit -m "feat: batch mode (add to batch, export one .apkg) with word audio"
```

---

## Self-Review

**Spec coverage:**
- Batch: collect words, add each with per-word example control, export one `.apkg` to one deck → Task 3 (`on_add`, `on_export`, `_export_batch`, `_preview_keyboard`, `export_button`). ✅
- Single word = batch of one → Task 3 (add then export). ✅
- Empty-batch export handled → Task 3 (`on_export` / `_export_batch`). ✅
- Word audio: native jpod101 → placeholder detect → TTS fallback → None → Task 1. ✅
- Word audio placement on front → Task 2 (front template `{{WordAudio}}`). ✅
- New note type so import isn't broken by the added field → Task 2 (`MODEL_ID = 1608310002`, name "Kanji Anki Bot 2"). ✅
- `CardSpec` = (word_info, glosses, example); batch stores specs, media resolved at export → Tasks 2 (`CardSpec`/`CardMedia`) + 3. ✅
- Error handling: word audio None → no word audio; media download fail → skip; graceful → Tasks 1 & 3. ✅
- Owner-only on every handler → Task 3 (all handlers call `owns`). ✅
- Testing per spec (is_placeholder, fallback, batch build, keyboard helpers) → Tasks 1–3. ✅

**Placeholder scan:** No TBD/TODO; every code step has complete code; every test step has real assertions.

**Type consistency:** `CardSpec(word_info, glosses, example)` and `CardMedia(image_path, sound_path, word_audio_path)` defined in Task 2 and used identically in Task 3. `build_apkg(items: list[tuple[CardSpec, CardMedia]], deck_name, out_path)` defined in Task 2, called that way in Task 3. `fetch_word_audio(word, reading) -> bytes | None` (Task 1) called as such in Task 3. `export_button` / `_preview_keyboard` signatures match their tests.

**Note on `on_text` custom-deck path:** after ✏️ Своя колода, the typed name routes to `_export_batch` (batch), consistent with `on_deck`. The old single-card `_build_and_send` is fully removed.
