# Verified API Findings (2026-07-22)

All endpoints below were tested live and confirmed working. No auth required
except OCR.space (free key).

## 1. Jisho — meaning + reading

`GET https://jisho.org/api/v1/search/words?keyword=<word>`

Response (verified for 今日):
- `data[0].japanese[0].word` → `"今日"`
- `data[0].japanese[0].reading` → `"きょう"` (kana)
- `data[0].senses[i].english_definitions` → `["today","this day"]`
- `data[0].senses[i].parts_of_speech` → `["Noun","Adverb (fukushi)"]`

Build the "Meaning" block by numbering each sense's `english_definitions`
joined by `; `.

## 2. kanjiapi.dev — per-kanji gloss (the "Kanji used" block)

`GET https://kanjiapi.dev/v1/kanji/<single-kanji-char>` (URL-encode the char)

Response (verified):
- 今 → `.meanings` = `["now"]`
- 日 → `.meanings` = `["Japan","counter for days","day","sun"]`

Call once per **kanji** character in the word (skip kana). Use the first
meaning (or first 1–2) for the gloss. Non-kanji chars have no entry (404) — skip.

> Note: Jisho's word API does NOT give per-kanji meanings; kanjiapi.dev is the
> source for the individual-kanji breakdown shown in the reference card.

## 3. ImmersionKit — example sentence + audio + image

**The old `api.immersionkit.com/look_up_dictionary` is retired (returns a
PythonAnywhere "Coming Soon" 404).** The current API is:

`GET https://apiv2.immersionkit.com/search?q=<word>&sort=sentence_length:asc&category=anime`

- `sort` must include order: use `sentence_length:asc` (shortest first).
- `q` is required (not `keyword`).

Response top-level keys: `category_count`, `deck_count`, `examples`,
`locale`, `dictionary_entries`, `exactMatch`.

Each `examples[i]` (verified):
- `id` → `"anime_castle_in_the_sky_000000015"`
- `sentence` → plain Japanese
- `sentence_with_furigana` → `"うん　今日[きょう]はひさしぶりに 忙[いそが]しいんだ"`
  (already in Anki furigana format `漢字[かな]` — feed to `{{furigana:…}}`)
- `translation` → English
- `image` → bare filename, e.g. `"A_CastleInTheSky_1_0.6.32.395.jpg"`
- `sound` → bare filename, e.g. `"A_CastleInTheSky_1_0.6.31.200-0.6.33.590.mp3"`
- `title` → deck id (snake_case), e.g. `"castle_in_the_sky"`

## 4. ImmersionKit media URL (verified HTTP 200 for both image + audio)

```
https://us-southeast-1.linodeobjects.com/immersionkit/media/<category>/<DISPLAY_TITLE>/media/<filename>
```

- `<category>` = the deck's category (anime/drama/games).
- `<DISPLAY_TITLE>` = human display name, URL-encoded (spaces → %20). This is
  **not** a transform of the snake_case `title`; it comes from a lookup table.
- The lookup table (deck id → {title, category}) was extracted from the
  ImmersionKit frontend bundle and saved to `src/data/immersionkit_decks.json`
  (95 decks). Example: `castle_in_the_sky` → `{"title":"Castle in the sky","category":"anime"}`.

Verified download:
`.../immersionkit/media/anime/Castle%20in%20the%20sky/media/A_CastleInTheSky_1_0.6.32.395.jpg`
→ HTTP 200, image/jpeg, 28 KB. Audio sibling → HTTP 200, audio/mpeg, 40 KB.

Re-extraction (if the deck list changes): fetch the Next.js chunk under
`https://www.immersionkit.com/_next/static/chunks/` that contains
`title:"…",category:"anime"` entries and regex them out (script in git history).

## 5. OCR.space — photo → Japanese text (documented contract)

`POST https://api.ocr.space/parse/image` (multipart/form-data)
- `apikey` = free key from https://ocr.space/ocrapi (register email → key)
- `language` = `jpn`
- `OCREngine` = `1` (engine 1 supports Japanese)
- `isOverlayRequired` = `false`
- `file` = the uploaded image bytes (or `base64Image=data:image/png;base64,…`)

Response: `ParsedResults[0].ParsedText`, plus `IsErroredOnProcessing`,
`ErrorMessage`, `OCRExitCode`. To be confirmed against a real Japanese image
during implementation (Task with a fixture image).

## 6. genanki + Hugging Face Spaces

- `genanki` builds `.apkg` with a custom `Model` (note type) and `Package`
  with `media_files` (downloaded audio + image). Standard library, pip-installable.
- Hugging Face **Docker Space** (free, no card) hosts the webhook bot 24/7.
  Telegram `setWebhook` → `https://<user>-<space>.hf.space/<secret-path>`.
