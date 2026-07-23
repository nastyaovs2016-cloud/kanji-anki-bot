import zipfile
from pathlib import Path

from app.card import format_meaning, format_kanji_block, deck_id_for, build_apkg, build_model
from app.models import WordInfo, KanjiGloss, Example, CardSpec, CardMedia


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


def test_model_has_word_audio_field_and_front_control():
    model = build_model()
    field_names = [f["name"] for f in model.fields]
    assert field_names == [
        "Word", "Reading", "Meaning", "KanjiUsed", "SentenceFurigana",
        "Translation", "Audio", "Image", "WordAudio",
    ]
    front = model.templates[0]["qfmt"]
    assert "{{WordAudio}}" in front          # word audio plays on the front


def test_build_apkg_single_card_no_media(tmp_path):
    spec = CardSpec(WordInfo("今日", "きょう", [["today"]]), [KanjiGloss("今", "now")], None)
    out = tmp_path / "deck.apkg"
    path = build_apkg([(spec, CardMedia())], "Test Deck", str(out))
    assert Path(path).exists()
    with zipfile.ZipFile(path) as z:
        assert "collection.anki2" in z.namelist()


def test_build_apkg_batch_with_word_audio_and_example(tmp_path):
    wav = tmp_path / "word.mp3"; wav.write_bytes(b"ID3word")
    img = tmp_path / "pic.jpg"; img.write_bytes(b"\xff\xd8\xff\xd9")
    snd = tmp_path / "clip.mp3"; snd.write_bytes(b"ID3clip")
    ex = Example("今日はいい天気", "今日[きょう]はいい 天気[てんき]", "Nice weather",
                 "pic.jpg", "clip.mp3", "castle_in_the_sky")
    spec1 = CardSpec(WordInfo("今日", "きょう", [["today"]]), [KanjiGloss("今", "now")], ex)
    media1 = CardMedia(image_path=str(img), sound_path=str(snd), word_audio_path=str(wav))
    wav2 = tmp_path / "word2.mp3"; wav2.write_bytes(b"ID3word2")
    spec2 = CardSpec(WordInfo("子供", "こども", [["child"]]), [KanjiGloss("子", "child")], None)
    media2 = CardMedia(word_audio_path=str(wav2))

    out = tmp_path / "batch.apkg"
    build_apkg([(spec1, media1), (spec2, media2)], "Test Deck", str(out))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    # media manifest + 4 media files (img, clip, word, word2) stored as "0".."3"
    assert "media" in names
    assert {"0", "1", "2", "3"}.issubset(set(names))
