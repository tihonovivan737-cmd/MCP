from __future__ import annotations

import re
import unicodedata

_MULTI_SPACE_RE = re.compile(r"[ \t\f\v]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_CTRL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def sanitize_text(text: str) -> str:
    """Нормализует текст перед эмбеддингом без потери смысловой структуры."""
    if not text:
        return ""

    s = unicodedata.normalize("NFKC", text)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\u00A0", " ").replace("\u2007", " ").replace("\u202F", " ")
    s = _CTRL_CHARS_RE.sub("", s)

    # Чистим лишние пробелы внутри строк, сохраняя переносы.
    lines = []
    for line in s.split("\n"):
        line = _MULTI_SPACE_RE.sub(" ", line).strip()
        lines.append(line)
    s = "\n".join(lines)

    # Ограничиваем "лесенку" пустых строк.
    s = _MULTI_NEWLINE_RE.sub("\n\n", s).strip()
    return s


def sanitize_texts(texts: list[str]) -> list[str]:
    return [sanitize_text(t) for t in texts]

