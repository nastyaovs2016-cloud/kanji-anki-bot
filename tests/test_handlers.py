from app.handlers import preview_text, deck_keyboard
from app.lookup import CardData
from app.models import WordInfo, KanjiGloss, Example


def _cd(with_example=True):
    ex = [Example("今日はいい天気", "今日[きょう]はいい 天気[てんき]",
                  "Nice weather", "i.jpg", "a.mp3", "castle_in_the_sky")] if with_example else []
    return CardData(WordInfo("今日", "きょう", [["today", "this day"]]),
                    [KanjiGloss("今", "now"), KanjiGloss("日", "sun")], ex)


def test_preview_text_includes_word_and_example():
    txt = preview_text(_cd(), 0)
    assert "今日" in txt
    assert "きょう" in txt
    assert "today" in txt
    assert "天気" in txt or "Nice weather" in txt


def test_preview_text_no_example():
    txt = preview_text(_cd(with_example=False), 0)
    assert "без примера" in txt.lower() or "нет примера" in txt.lower()


def test_deck_keyboard_has_button_per_deck():
    kb = deck_keyboard(["A", "B"])
    flat = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "A" in flat and "B" in flat
