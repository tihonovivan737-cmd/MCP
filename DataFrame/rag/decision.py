"""Decision layer: фильтрация нерелевантных запросов перед вызовом LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_DEFAULT_VAGUE = re.compile(
    r"\b(наш[аеи]?|наше|наш|моя?|этот объект|данное предприятие|у нас|они|оно)\b",
    re.IGNORECASE,
)


@dataclass
class DecisionResult:
    status: str  # "ok" | "no_answer" | "need_clarify"
    message: str | None = None
    top_score: float = 0.0


@dataclass
class DecisionPolicy:
    """
    Фильтрует запросы по score Qdrant, длине и расплывчатым местоимениям.

    Настройка через env:
        DECISION_MIN_SCORE    — нижний порог (по умолчанию 0.35)
        DECISION_STRONG_SCORE — порог уверенности для коротких запросов (0.55)
    """

    vague_pattern: re.Pattern | None = field(default_factory=lambda: _DEFAULT_VAGUE)

    no_results_message: str = "По вашему запросу ничего не найдено в базе знаний."
    low_score_message: str = (
        "Не найдено достаточно релевантных данных.\n"
        "Попробуйте уточнить формулировку запроса."
    )
    vague_message: str = (
        "Уточните, пожалуйста, конкретный объект, организацию или показатель."
    )
    too_short_message: str = "Запрос слишком общий. Уточните детали."

    def __call__(
        self,
        hits: list,
        query: str,
        *,
        min_score: float,
        strong_score: float,
    ) -> DecisionResult:
        if not hits:
            return DecisionResult(status="no_answer", message=self.no_results_message)

        top_score = float(getattr(hits[0], "score", 0.0))

        if top_score < min_score:
            return DecisionResult(
                status="no_answer",
                message=self.low_score_message,
                top_score=top_score,
            )

        if self.vague_pattern and self.vague_pattern.search(query):
            return DecisionResult(
                status="need_clarify",
                message=self.vague_message,
                top_score=top_score,
            )

        words = query.strip().split()
        if len(words) <= 3 and top_score < strong_score:
            return DecisionResult(
                status="need_clarify",
                message=self.too_short_message,
                top_score=top_score,
            )

        return DecisionResult(status="ok", message=None, top_score=top_score)
