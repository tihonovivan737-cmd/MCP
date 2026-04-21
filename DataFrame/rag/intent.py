"""Intent classifier: проверяет релевантность запроса домену МСП до поиска в Qdrant."""

from __future__ import annotations

import re
import logging

from .config import Settings

logger = logging.getLogger(__name__)

_MSP_KEYWORDS = re.compile(
    r"бизнес|предпринимател|мсп|ип\b|ооо|субсидия|субсидии|грант|займ|кредит|налог|"
    r"открыт|регистр|поддержк|финансир|экспорт|обучени|имуществ|льгот|самозанят|"
    r"ремесл|кооператив|фонд|микрофинанс|лизинг|гарантия|инновац|стартап|"
    r"работодател|сотрудник|бухгалтер|патент|лицензи|сертификат|банк|инвестиц",
    re.IGNORECASE,
)


def classify_intent(question: str, settings: Settings) -> bool:
    """
    Возвращает True если вопрос релевантен домену МСП, False иначе.
    Использует keyword-matching вместо LLM — быстро и без дополнительного вызова Ollama.
    """
    if len(question.strip()) < 5:
        return False
    match = bool(_MSP_KEYWORDS.search(question))
    logger.debug("Intent classify (keywords): %r -> %s", question, match)
    return match
