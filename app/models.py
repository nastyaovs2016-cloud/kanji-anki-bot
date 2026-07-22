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
