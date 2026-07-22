# Kanji → Anki Telegram Bot — Design

**Date:** 2026-07-22
**Status:** Approved for planning

## Purpose

A Telegram bot that turns a Japanese word into a ready-to-import Anki card.
The user sends a kanji/word (as text or a photo) and receives a `.apkg` deck file
containing one card formatted like their existing Anki template (Meaning, Kanji
used, Example sentence with furigana, English translation, audio, image).

The bot must run **for free**, **24/7**, and **without depending on the user's
MacBook**. The user studies on **AnkiMobile (iPhone)**.

## User Flow

1. User sends the bot a word as **text** (`今日`) or a **photo** of the word.
2. If a photo: bot runs OCR and shows what it recognized for confirmation
   ("Нашёл: 今日 (きょう) — today. Собрать карточку?").
3. Bot asks, via inline buttons, **which deck** to use (preset list of the user's
   deck names + option to type a custom name).
4. Bot fetches card data (see Data Sources) and shows a preview of the example
   sentence, with a **"🔀 другой пример"** button to cycle to a shorter/other
   ImmersionKit example.
5. On confirmation, the bot builds a `.apkg` deck file (with audio + image
   embedded) and sends it to the chat.
6. User taps the file → "Открыть в AnkiMobile" → import. The card lands in the
   chosen deck with all media.

## Data Sources

All free, no login, no browser required.

| Card block                     | Source          |
|--------------------------------|-----------------|
| Meaning (numbered definitions) | Jisho API       |
| Kanji used (今 = now, 日 = sun) | Jisho API       |
| Example sentence (Japanese)    | ImmersionKit API|
| English translation of example | ImmersionKit API|
| Audio (example sentence)       | ImmersionKit API|
| Image (anime frame)            | ImmersionKit API|
| Reading (furigana, きょう)      | Jisho API       |

**Design decision:** jpdb.io was the user's original source but requires login and
has bot protection, which is incompatible with free, browser-less, MacBook-free
hosting. Jisho.org provides equivalent Meaning + Kanji-breakdown data via a free
public API and is used instead. This was explicitly approved by the user.

## Card Template (Anki note type)

Recreates the user's existing card (see reference screenshots).

**Fields:**
- `Word` — 今日
- `Reading` — きょう
- `Meaning` — numbered list ("1. today; this day\n2. these days; recently")
- `KanjiUsed` — per-kanji gloss (今 now / 日 sun)
- `ExampleJa` — sentence with furigana markup, e.g. `お店[たな]　今日[きょう]からなんですか？`
- `ExampleEn` — "Is the shop opening today?"
- `Audio` — `[sound:<file>.mp3]`
- `Image` — `<img src="<file>.jpg">`

**Front:** `Word` + `ExampleJa` (plain).
**Back:** all blocks under headings "Meaning", "Kanji used", "Example", audio play
control, image at the bottom — matching the screenshot layout (centered, serif-ish
headings). Furigana rendered via Anki's `{{furigana:ExampleJa}}` filter.

Note type + deck are packaged with genanki so AnkiMobile imports cleanly.

## Technical Architecture

- **Language:** Python (needed for `genanki` to build `.apkg` with embedded media).
- **Bot framework:** a standard Telegram bot library (e.g. `python-telegram-bot`
  or `aiogram`), running in **webhook** mode so it fits a single web service.
- **Hosting:** Hugging Face Spaces — free, no credit card, runs 24/7, deployed via
  web UI. The user performs the one-time (~15 min) deploy following a written guide;
  the assistant provides all code and instructions but cannot deploy into the
  user's account.
- **OCR (photo input):** OCR.space free API (Japanese engine, free key, no card).
  Text input is always the reliable fallback if OCR misreads.
- **Anki delivery:** the bot sends a `.apkg` file to the Telegram chat. AnkiMobile
  has no over-the-air card intake, so file import is the only viable path on iPhone.
- **Secrets/config:** Telegram bot token, OCR.space key, and the user's deck-name
  list stored as environment variables / Space secrets.

### Components (each independently understandable/testable)

1. **Telegram handler** — receives messages (text/photo), drives the conversation,
   renders inline keyboards, sends the final file. Depends on: OCR, data fetchers,
   card builder.
2. **OCR module** — photo bytes → recognized Japanese string. Depends on: OCR.space.
3. **Jisho client** — word → { reading, meanings[], kanji breakdown[] }.
4. **ImmersionKit client** — word → list of { sentence_ja, sentence_en, audio_url,
   image_url }, sorted by length ascending; supports picking the next candidate.
5. **Card builder** — assembled data + chosen deck name → `.apkg` bytes, with audio
   and image downloaded and embedded via genanki.
6. **Config** — deck list, tokens, keys.

## Error Handling

- **No ImmersionKit example found:** build the card with Meaning + Kanji only,
  warn the user that no example/audio/image was attached.
- **OCR fails or returns garbage:** show what was recognized and let the user
  correct it by typing the word.
- **Jisho returns nothing:** tell the user the word wasn't found; no card built.
- **Media download fails:** attach the card without the failing media, warn.
- **Network/API errors:** catch and report a friendly message; never crash the bot.

## Testing

- Unit tests for each client (Jisho, ImmersionKit, OCR) against recorded/sample
  responses.
- Unit test for the card builder: given fixed data, produces a valid `.apkg`
  (openable, correct fields, media present).
- A manual end-to-end check: send `今日`, receive `.apkg`, import into AnkiMobile,
  confirm it matches the reference screenshot.

## Out of Scope (v1)

- Direct/over-the-air card insertion into AnkiMobile (not technically possible).
- Bulk import of many words at once.
- Editing existing cards.
- Scraping jpdb.io directly.

## Deliverables

1. Bot source code (all components above).
2. `requirements.txt` / Space configuration.
3. Step-by-step deployment guide for Hugging Face Spaces (create bot with
   @BotFather, get OCR.space key, create the Space, set secrets, set webhook).
4. The reference Anki note type reproduced faithfully.
