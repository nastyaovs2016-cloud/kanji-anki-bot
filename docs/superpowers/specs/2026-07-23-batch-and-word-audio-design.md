# Batch Mode + Word Audio — Design

**Date:** 2026-07-23
**Status:** Approved for planning
**Extends:** the deployed Kanji→Anki bot (see 2026-07-22 spec).

## Purpose

Two additions to the existing bot:

1. **Batch mode** — collect several words into a "batch", then export them all as
   one `.apkg` (one card per word) into a single chosen deck, instead of exporting
   one card at a time.
2. **Word audio on the card front** — add a second audio to each card: the
   pronunciation of the word itself (dictionary form), on the front side where the
   word is shown. The example-sentence audio on the back stays as-is.

## Feature 1: Batch Mode

### User flow

1. User sends a word (text or photo) — same preview as today: word/reading/meaning
   + the current example, with a **🔀 Другой пример** button to cycle examples.
2. The preview now also has **➕ Добавить в партию**. Tapping it appends the current
   word (with its chosen example) to the user's batch. The bot replies
   "✅ Добавлено (в партии: N)" with a **📦 Выгрузить (N)** button.
3. User repeats for more words (each reviewed and added individually — the user
   keeps per-word control of the example).
4. Tapping **📦 Выгрузить** asks for the deck **once** (existing deck buttons +
   ✏️ custom), then builds **one** `.apkg` containing all N cards for that deck,
   sends it, and clears the batch.

### Rules

- One deck per batch (to send to different decks, the user makes separate batches).
- A single word is just a batch of one (add → export).
- The batch lives in `context.user_data` (per user). It survives across messages
  within the running bot; it is not persisted to disk (a bot restart / long sleep
  clears it — acceptable for personal use). If a user taps 📦 Выгрузить with an
  empty batch, the bot says the batch is empty.
- Owner-only, as everywhere else.

## Feature 2: Word Audio

### Source (verified 2026-07-23)

For each word, fetch the word's pronunciation audio:

1. **Native first — JapanesePod101:**
   `GET https://assets.languagepod101.com/dictionary/japanese/audiomp3.php?kanji=<word>&kana=<reading>`
   (follow redirects, browser User-Agent). Real words return a small mp3 (~1–3 KB).
2. **Detect "not found":** missing words return a fixed placeholder mp3 —
   **52288 bytes, md5 `7e2c2f954ef6051373ba916f000168dc`**. If the response matches
   the placeholder (by size and/or md5), treat it as "no native audio".
3. **Fallback — synthetic TTS (Google Translate TTS):**
   `GET https://translate.google.com/translate_tts?ie=UTF-8&q=<word>&tl=ja&client=tw-ob`
   (browser User-Agent). Always returns audio.
4. If both fail (network/IP block), the card is built without word audio.

`<reading>` comes from Jisho (`WordInfo.reading`). Requests use the same
browser-header approach already used for ImmersionKit, since server/datacenter IPs
can be blocked otherwise; all failures degrade gracefully.

## Card Template Change

Add a 9th field `WordAudio` to the note type.

- **Front:** `Word` + **`{{WordAudio}}`** (the ▶ play control for the word's
  pronunciation) + the plain example sentence (`{{kanji:SentenceFurigana}}`).
- **Back:** unchanged (Meaning, Kanji used, Example with its own audio, translation,
  image).
- `WordAudio` field holds `[sound:<file>.mp3]`; the file is added to the package's
  media. Empty when no word audio was obtained.

Changing the note type's field list is backward-compatible for new imports; existing
cards are unaffected.

## Components

- **`app/word_audio.py`** (new):
  - `is_placeholder(content: bytes) -> bool` — pure; true when `content` is the
    jpod101 "not found" placeholder (size 52288 / known md5).
  - `fetch_word_audio(word: str, reading: str) -> bytes | None` — I/O; jpod101 →
    placeholder check → Google TTS fallback → `None`.
- **`app/card.py`** (modify):
  - Add `WordAudio` field + front-template play control.
  - Generalize building to a batch: `build_apkg(cards: list[CardSpec], deck_name,
    out_path)` where `CardSpec` bundles one card's data (word_info, glosses,
    example, and resolved media paths incl. word audio). A single card is a
    one-element list.
- **`app/models.py`** (modify): add a `CardSpec` dataclass holding one finalized
  batch item: `word_info: WordInfo`, `glosses: list[KanjiGloss]`,
  `example: Example | None`. The batch is `list[CardSpec]`. (Not `CardData`, which
  carries all candidate examples; a batch item records only the chosen one.)
- **`app/handlers.py`** (modify): batch state in `user_data`; ➕ Добавить / 📦
  Выгрузить buttons and their callbacks; at export, download each card's media
  (example image/sound + word audio) and call the batch builder; deck chosen once.
- **`app/lookup.py`**: unchanged for data gathering; word audio is fetched at
  build/export time (keeps batch state small — store the chosen example, not bytes).

## Data Flow (export)

For each item in the batch: resolve example media URLs (existing `media_urls`) →
download image/sound → `fetch_word_audio(word, reading)` → write temp files →
assemble one `genanki.Note` → collect all media → one `genanki.Package` → send →
clean up temp files → clear batch.

## Error Handling

- Word audio unavailable → card built without it (front shows word, no ▶).
- Example missing (as today) → card without example/its audio/image.
- A single word failing to gather (Jisho miss) → not added; user told; batch intact.
- Media/network errors during export → that media skipped, card still built; a
  friendly message if a whole word can't be built.
- Empty batch on export → "партия пуста".

## Testing

- `word_audio`: unit-test `is_placeholder` against the known placeholder signature
  and against a real (non-placeholder) sample; test `fetch_word_audio` fallback
  logic with monkeypatched HTTP (native-hit, placeholder→TTS, both-fail→None).
- `card`: build a 2-note `.apkg` → zip contains a valid collection and both notes'
  media; assert the front template references `WordAudio`; a card with no word
  audio omits the sound tag but still builds.
- `handlers`: pure helpers — batch summary text ("в партии: N"), and that adding
  appends / exporting clears.

## Out of Scope

- Persisting batches across bot restarts.
- Per-word decks within one batch.
- Editing/removing individual items from a batch (v1: add + export; if the user
  wants to drop a word, they export and delete it in Anki, or restart the batch).
