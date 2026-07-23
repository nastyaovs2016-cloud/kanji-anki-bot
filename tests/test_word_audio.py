from pathlib import Path

import app.word_audio as wa

FIX = Path(__file__).parent / "fixtures"


class _Resp:
    def __init__(self, content=b"", status=200):
        self.content = content
        self.status_code = status


def test_is_placeholder_true_for_fixture():
    data = (FIX / "jpod_placeholder.mp3").read_bytes()
    assert wa.is_placeholder(data) is True


def test_is_placeholder_false_for_other_bytes():
    assert wa.is_placeholder(b"real audio bytes") is False


def test_fetch_returns_native_when_present(monkeypatch):
    def fake_get(url, **kw):
        assert "languagepod101" in url
        return _Resp(b"NATIVE-AUDIO")
    monkeypatch.setattr(wa.requests, "get", fake_get)
    assert wa.fetch_word_audio("今日", "きょう") == b"NATIVE-AUDIO"


def test_fetch_falls_back_to_tts_on_placeholder(monkeypatch):
    placeholder = (FIX / "jpod_placeholder.mp3").read_bytes()

    def fake_get(url, **kw):
        if "languagepod101" in url:
            return _Resp(placeholder)          # native missing → placeholder
        return _Resp(b"TTS-AUDIO")             # google tts
    monkeypatch.setattr(wa.requests, "get", fake_get)
    assert wa.fetch_word_audio("峠", "とうげ") == b"TTS-AUDIO"


def test_fetch_returns_none_when_both_fail(monkeypatch):
    def fake_get(url, **kw):
        raise wa.requests.RequestException("boom")
    monkeypatch.setattr(wa.requests, "get", fake_get)
    assert wa.fetch_word_audio("今日", "きょう") is None
