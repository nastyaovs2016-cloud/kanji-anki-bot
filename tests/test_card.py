import zipfile
from pathlib import Path

from app.card import format_meaning, format_kanji_block, deck_id_for, build_apkg
from app.models import WordInfo, KanjiGloss, Example


def test_format_meaning_numbers_senses():
    out = format_meaning([["today", "this day"], ["nowadays", "recently"]])
    assert out == "1. today; this day<br>2. nowadays; recently"


def test_format_kanji_block():
    out = format_kanji_block([KanjiGloss("今", "now"), KanjiGloss("日", "sun")])
    assert out == "今 now<br>日 sun"


def test_deck_id_is_stable_and_int():
    a = deck_id_for("Японский::Слова")
    b = deck_id_for("Японский::Слова")
    assert a == b and isinstance(a, int)
    assert a != deck_id_for("Other")


def test_build_apkg_without_media(tmp_path):
    wi = WordInfo(word="今日", reading="きょう", meanings=[["today"]])
    out = tmp_path / "deck.apkg"
    path = build_apkg(wi, [KanjiGloss("今", "now")], None, None, None,
                      "Test Deck", str(out))
    assert Path(path).exists()
    # .apkg is a zip containing an SQLite collection
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    assert "collection.anki2" in names


def test_build_apkg_with_media(tmp_path):
    img = tmp_path / "pic.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")          # minimal jpeg-ish bytes
    snd = tmp_path / "clip.mp3"
    snd.write_bytes(b"ID3")
    wi = WordInfo(word="今日", reading="きょう", meanings=[["today"]])
    ex = Example("今日はいい天気", "今日[きょう]はいい 天気[てんき]", "Nice weather today",
                 "pic.jpg", "clip.mp3", "castle_in_the_sky")
    out = tmp_path / "deck.apkg"
    build_apkg(wi, [KanjiGloss("今", "now")], ex, str(img), str(snd),
               "Test Deck", str(out))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    # media are stored as index files "0","1" plus a media manifest
    assert "media" in names
    assert "0" in names and "1" in names
