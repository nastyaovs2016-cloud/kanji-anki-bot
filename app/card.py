from __future__ import annotations

import hashlib
import os

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
