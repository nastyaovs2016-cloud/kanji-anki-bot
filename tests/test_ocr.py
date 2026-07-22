from app.ocr import parse_ocr


def test_parse_ocr_success():
    data = {
        "IsErroredOnProcessing": False,
        "ParsedResults": [{"ParsedText": "今日\r\n"}],
    }
    assert parse_ocr(data) == "今日"


def test_parse_ocr_error_returns_empty():
    assert parse_ocr({"IsErroredOnProcessing": True, "ErrorMessage": ["bad"]}) == ""


def test_parse_ocr_no_results():
    assert parse_ocr({"IsErroredOnProcessing": False, "ParsedResults": []}) == ""
