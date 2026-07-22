import app.lookup as lookup
from app.models import WordInfo, KanjiGloss, Example


def test_gather_returns_none_when_jisho_empty(monkeypatch):
    monkeypatch.setattr(lookup.jisho, "fetch_word", lambda w: None)
    monkeypatch.setattr(lookup.kanji, "fetch_breakdown", lambda w: [])
    monkeypatch.setattr(lookup.immersionkit, "fetch_examples", lambda w: [])
    assert lookup.gather("今日") is None


def test_gather_assembles(monkeypatch):
    wi = WordInfo("今日", "きょう", [["today"]])
    ex = [Example("s", "s[k]", "t", "i.jpg", "a.mp3", "castle_in_the_sky")]
    monkeypatch.setattr(lookup.jisho, "fetch_word", lambda w: wi)
    monkeypatch.setattr(lookup.kanji, "fetch_breakdown", lambda w: [KanjiGloss("今", "now")])
    monkeypatch.setattr(lookup.immersionkit, "fetch_examples", lambda w: ex)
    cd = lookup.gather("今日")
    assert cd.word_info is wi
    assert cd.glosses[0].char == "今"
    assert cd.examples == ex
