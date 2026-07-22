import json
from pathlib import Path
from app.kanji import is_kanji, extract_kanji, parse_meaning

FIX = Path(__file__).parent / "fixtures"


def test_is_kanji():
    assert is_kanji("今") is True
    assert is_kanji("き") is False   # hiragana
    assert is_kanji("A") is False


def test_extract_kanji_dedups_and_keeps_order():
    assert extract_kanji("今日今") == ["今", "日"]
    assert extract_kanji("食べる") == ["食"]
    assert extract_kanji("きょう") == []


def test_parse_meaning_uses_first():
    data = json.loads((FIX / "kanjiapi_hi.json").read_text(encoding="utf-8"))
    assert parse_meaning(data) == data["meanings"][0]
