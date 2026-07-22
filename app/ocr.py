from __future__ import annotations

import requests

API = "https://api.ocr.space/parse/image"


def parse_ocr(data: dict) -> str:
    if data.get("IsErroredOnProcessing"):
        return ""
    results = data.get("ParsedResults") or []
    if not results:
        return ""
    text = results[0].get("ParsedText", "") or ""
    return "".join(text.split())


def ocr_image(image_bytes: bytes, api_key: str) -> str:
    resp = requests.post(
        API,
        files={"file": ("image.png", image_bytes)},
        data={
            "apikey": api_key,
            "language": "jpn",
            "OCREngine": "1",
            "isOverlayRequired": "false",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return parse_ocr(resp.json())
