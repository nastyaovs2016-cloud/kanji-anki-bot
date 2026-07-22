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


def test_parse_meaning_takes_first_clean_meanings():
    # 日 → ['Japan','counter for days','day','sun']; the "counter for" gloss is
    # dropped, and up to two clean meanings are joined.
    data = json.loads((FIX / "kanjiapi_hi.json").read_text(encoding="utf-8"))
    assert parse_meaning(data) == "Japan; day"


def test_parse_meaning_skips_junk_leading_meaning():
    # 子 leads with the obscure zodiac-hour gloss "11PM-1AM"; it must be skipped
    # so the block shows "child", not the time range.
    data = {"meanings": ["11PM-1AM", "child", "first sign of Chinese zodiac", "sign of the rat"]}
    assert parse_meaning(data) == "child"


def test_parse_meaning_falls_back_when_all_junk():
    data = {"meanings": ["11PM-1AM"]}
    assert parse_meaning(data) == "11PM-1AM"


def test_parse_meaning_empty():
    assert parse_meaning({"meanings": []}) == ""
