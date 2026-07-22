from __future__ import annotations

import logging
from dataclasses import dataclass

from app import immersionkit, jisho, kanji
from app.models import Example, KanjiGloss, WordInfo

logger = logging.getLogger(__name__)


@dataclass
class CardData:
    word_info: WordInfo
    glosses: list[KanjiGloss]
    examples: list[Example]


def gather(word: str) -> CardData | None:
    word_info = jisho.fetch_word(word)
    if word_info is None:
        return None
    glosses = kanji.fetch_breakdown(word)
    try:
        examples = immersionkit.fetch_examples(word)
    except Exception as exc:
        logger.warning("ImmersionKit lookup failed for %r: %s", word, exc)
        examples = []
    else:
        if not examples:
            logger.info("ImmersionKit returned no examples for %r", word)
    return CardData(word_info=word_info, glosses=glosses, examples=examples)
