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


def _build_note(model: genanki.Model, spec: CardSpec, media: CardMedia) -> tuple[genanki.Note, list[str]]:
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
