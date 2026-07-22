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
