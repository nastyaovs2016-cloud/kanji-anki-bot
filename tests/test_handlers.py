from app.handlers import preview_text, deck_keyboard, _preview_keyboard, export_button
from app.lookup import CardData
from app.models import WordInfo, KanjiGloss, Example


def _cd(with_example=True):
    ex = [Example("今日はいい天気", "今日[きょう]はいい 天気[てんき]",
                  "Nice weather", "i.jpg", "a.mp3", "castle_in_the_sky")] if with_example else []
    return CardData(WordInfo("今日", "きょう", [["today", "this day"]]),
                    [KanjiGloss("今", "now"), KanjiGloss("日", "sun")], ex)


def test_preview_text_includes_word_and_example():
    txt = preview_text(_cd(), 0)
    assert "今日" in txt and "きょう" in txt and "today" in txt
    assert "天気" in txt or "Nice weather" in txt


def test_preview_text_no_example():
    txt = preview_text(_cd(with_example=False), 0)
    assert "без примера" in txt.lower() or "нет примера" in txt.lower()


def test_deck_keyboard_has_button_per_deck():
    kb = deck_keyboard(["A", "B"])
    flat = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "A" in flat and "B" in flat


def test_preview_keyboard_offers_add_to_batch():
    kb = _preview_keyboard(multiple_examples=True)
    datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "add" in datas          # ➕ Добавить в партию
    assert "next" in datas         # 🔀 shown when multiple examples


def test_preview_keyboard_single_example_has_no_shuffle():
    kb = _preview_keyboard(multiple_examples=False)
    datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "add" in datas
    assert "next" not in datas


def test_export_button_shows_count_and_callback():
    kb = export_button(3)
    btn = kb.inline_keyboard[0][0]
    assert "3" in btn.text
    assert btn.callback_data == "export"
