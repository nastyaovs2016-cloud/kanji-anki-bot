import json
from pathlib import Path
from app.jisho import parse_word

FIX = Path(__file__).parent / "fixtures"


def test_parse_word_kyou():
    data = json.loads((FIX / "jisho_kyou.json").read_text(encoding="utf-8"))
    wi = parse_word(data)
    assert wi is not None
    assert wi.word == "今日"
    assert wi.reading == "きょう"
    # first sense contains "today"
    assert "today" in wi.meanings[0]
    assert len(wi.meanings) >= 1


def test_parse_word_empty_returns_none():
    assert parse_word({"data": []}) is None
