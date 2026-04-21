"""Реранкер на основе CrossEncoder (sentence-transformers)."""

from __future__ import annotations

from functools import lru_cache

# Многоязычная модель MS MARCO — хорошо работает с русским.
# Меняется через env RERANK_MODEL.
DEFAULT_RERANK_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


@lru_cache(maxsize=2)
def _cross_encoder(model_name: str):
    from sentence_transformers import CrossEncoder  # type: ignore

    return CrossEncoder(model_name)


def rerank(query: str, hits: list, *, model_name: str, top_n: int) -> list:
    """
    Переранжирует hits по score CrossEncoder.

    hits — список qm.ScoredPoint (payload содержит поле "text" или "row_json").
    Возвращает top_n лучших хитов, отсортированных по убыванию релевантности.
    """
    if not hits:
        return hits

    ce = _cross_encoder(model_name)

    texts = []
    for h in hits:
        pl = h.payload or {}
        text = str(pl.get("text") or pl.get("row_json") or "")[:2000]
        texts.append(text)

    scores = ce.predict([(query, t) for t in texts])
    ranked = sorted(zip(scores, hits), key=lambda x: x[0], reverse=True)
    return [h for _, h in ranked[:top_n]]
