import json
from pathlib import Path
from app.immersionkit import parse_examples, media_urls
from app.config import load_deck_map

FIX = Path(__file__).parent / "fixtures"


def test_parse_examples_fields():
    data = json.loads((FIX / "immersionkit_kyou.json").read_text(encoding="utf-8"))
    examples = parse_examples(data)
    assert len(examples) > 0
    ex = examples[0]
    assert ex.sentence
    assert "[" in ex.sentence_furigana        # furigana markup present
    assert ex.translation
    assert ex.image_file.endswith(".jpg")
    assert ex.sound_file.endswith(".mp3")
    assert ex.deck_id                          # snake_case title


def test_media_urls_builds_encoded_path():
    ex = type("E", (), {
        "image_file": "A_CastleInTheSky_1_0.6.32.395.jpg",
        "sound_file": "A_CastleInTheSky_1_0.6.31.200-0.6.33.590.mp3",
        "deck_id": "castle_in_the_sky",
    })()
    img, snd = media_urls(ex, load_deck_map())
    assert img == (
        "https://us-southeast-1.linodeobjects.com/immersionkit/media/"
        "anime/Castle%20in%20the%20sky/media/A_CastleInTheSky_1_0.6.32.395.jpg"
    )
    assert snd.endswith(".mp3")
    assert "Castle%20in%20the%20sky" in snd


def test_media_urls_unknown_deck_returns_none():
    ex = type("E", (), {"image_file": "x.jpg", "sound_file": "x.mp3", "deck_id": "nope"})()
    assert media_urls(ex, load_deck_map()) == (None, None)
