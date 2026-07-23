from __future__ import annotations

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
