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
        specs = list(batch)
        n = len(specs)
        await chat.send_message(f"⏳ Собираю {n} карт.…")
        temp_paths: list[str] = []
        out = None
        try:
            items: list[tuple[CardSpec, CardMedia]] = []
            for spec in specs:
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
            first = specs[0].word_info.word
            fname = f"{first}_{len(specs)}.apkg" if len(specs) > 1 else f"{first}.apkg"
            with open(out, "rb") as f:
                await chat.send_document(
                    f, filename=fname,
                    caption=f"Готово: {len(specs)} карт. → «{deck_name}». Открой в AnkiMobile.")
            del batch[:n]
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
