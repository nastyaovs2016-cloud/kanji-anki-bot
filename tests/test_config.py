import os
import app.config as config


def test_settings_parses_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("OCR_SPACE_API_KEY", "key")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_ID", "42")
    monkeypatch.setenv("DECK_NAMES", "A, B ,C")
    s = config.settings()
    assert s.bot_token == "tok"
    assert s.ocr_api_key == "key"
    assert s.owner_id == 42
    assert s.deck_names == ["A", "B", "C"]  # trimmed, split on comma


def test_deck_map_has_known_deck():
    m = config.load_deck_map()
    assert m["castle_in_the_sky"]["title"] == "Castle in the sky"
    assert m["castle_in_the_sky"]["category"] == "anime"
    assert len(m) >= 90
