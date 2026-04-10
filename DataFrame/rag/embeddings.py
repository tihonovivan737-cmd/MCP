from __future__ import annotations

from functools import lru_cache

from .config import Settings
from .text_sanitizer import sanitize_texts


@lru_cache(maxsize=4)
def _model(name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name)


def _is_e5_family(model_name: str) -> bool:
    """Семейство E5 (intfloat/*e5*, и т.п.) ожидает префиксы query/passage."""
    return "e5" in model_name.lower()


def _apply_instruction_prefixes(texts: list[str], model_name: str, *, is_query: bool) -> list[str]:
    """E5 обучены с инструкциями query/passage — без них качество заметно хуже."""
    if not _is_e5_family(model_name):
        return texts
    prefix = "query: " if is_query else "passage: "
    return [prefix + t for t in texts]


def embed_texts(
    texts: list[str],
    settings: Settings,
    *,
    is_query: bool = False,
) -> list[list[float]]:
    if not texts:
        return []
    safe = sanitize_texts(texts) if settings.text_sanitizer_enabled else texts
    safe = [t if t else " " for t in safe]
    safe = _apply_instruction_prefixes(safe, settings.embedding_model, is_query=is_query)
    model = _model(settings.embedding_model)
    name_l = settings.embedding_model.lower()
    batch = 4 if "large" in name_l else 16
    vectors = model.encode(
        safe,
        batch_size=batch,
        show_progress_bar=len(texts) > 16,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return [v.tolist() for v in vectors]


def embedding_dim(settings: Settings) -> int:
    m = _model(settings.embedding_model)
    return int(m.get_sentence_embedding_dimension())
