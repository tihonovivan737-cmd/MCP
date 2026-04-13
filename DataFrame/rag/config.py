from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _env_qdrant_url() -> str | None:
    """Если задан QDRANT_URL — подключаемся к серверу (в т.ч. без Docker: бинарь Qdrant). Иначе — локальный embedded."""
    v = os.environ.get("QDRANT_URL", "").strip()
    return v if v else None


def _env_database_url() -> str | None:
    v = os.environ.get("DATABASE_URL", "").strip()
    return v if v else None


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


@dataclass
class Settings:
    project_root: Path = field(default_factory=_project_root)
    library_dir: Path | None = None
    knowledge_csv: Path | None = None
    pdf_paths: list[Path] = field(default_factory=list)

    qdrant_url: str | None = field(default_factory=_env_qdrant_url)
    qdrant_local_path: Path | None = None
    # postgresql://user:pass@host:5432/dbname — см. scripts/init_db.py
    database_url: str | None = field(default_factory=_env_database_url)
    # Файлы PDF/XLSX/CSV в таблице source_documents; индексация читает из БД
    source_files_in_postgres: bool = field(default_factory=lambda: _env_bool("SOURCE_FILES_IN_POSTGRES", False))
    guide_xlsx_document: str = field(
        default_factory=lambda: os.environ.get("GUIDE_XLSX_DOCUMENT", "Путеводитель.xlsx").strip()
        or "Путеводитель.xlsx",
    )
    knowledge_csv_document: str = field(
        default_factory=lambda: os.environ.get("KNOWLEDGE_CSV_DOCUMENT", "knowledge_base.csv").strip()
        or "knowledge_base.csv",
    )
    qdrant_collection: str = field(
        default_factory=lambda: os.environ.get("QDRANT_COLLECTION", "support_kb"),
    )

    # multilingual-e5-*: префиксы query:/passage: — rag/embeddings.py
    # Умолчание: large (максимум качества среди E5-многоязычных; тяжёлая).
    # Легче: intfloat/multilingual-e5-base | MiniLM — через EMBEDDING_MODEL
    embedding_model: str = field(
        default_factory=lambda: os.environ.get(
            "EMBEDDING_MODEL",
            "intfloat/multilingual-e5-large",
        ),
    )
    text_sanitizer_enabled: bool = field(default_factory=lambda: _env_bool("TEXT_SANITIZER_ENABLED", True))

    ollama_url: str = field(
        default_factory=lambda: (
            os.environ.get("OLLAMA_BASE_URL")
            or os.environ.get("OLLAMA_HOST")
            or "http://127.0.0.1:11434"
        ),
    )
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "qwen2.5:3b"))
    # Режим размышления в Ollama (/api/chat, /api/generate): см. docs.ollama.com/capabilities/thinking
    ollama_think: bool = field(default_factory=lambda: _env_bool("OLLAMA_THINK", False))

    retrieve_top_k: int = field(default_factory=lambda: int(os.environ.get("RETRIEVE_TOP_K", "3")))

    # Decision layer
    decision_min_score: float = field(default_factory=lambda: float(os.environ.get("DECISION_MIN_SCORE", "0.35")))
    decision_strong_score: float = field(default_factory=lambda: float(os.environ.get("DECISION_STRONG_SCORE", "0.55")))

    # Reranker (по умолчанию выключен)
    use_rerank: bool = field(default_factory=lambda: _env_bool("USE_RERANK", False))
    rerank_model: str = field(
        default_factory=lambda: os.environ.get(
            "RERANK_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
        )
    )
    rerank_fetch_k: int = field(default_factory=lambda: int(os.environ.get("RERANK_FETCH_K", "20")))

    pdf_chunk_max_chars: int = field(
        default_factory=lambda: int(os.environ.get("PDF_CHUNK_MAX_CHARS", "2800")),
    )
    pdf_chunk_overlap: int = field(
        default_factory=lambda: int(os.environ.get("PDF_CHUNK_OVERLAP", "200")),
    )

    def __post_init__(self) -> None:
        if self.library_dir is None:
            self.library_dir = self.project_root / "Library"
        if self.qdrant_local_path is None:
            self.qdrant_local_path = self.library_dir / "qdrant_local"
        qp = os.environ.get("QDRANT_PATH", "").strip()
        if qp:
            self.qdrant_local_path = Path(qp)
        if self.knowledge_csv is None:
            self.knowledge_csv = self.library_dir / "knowledge_base.csv"
        u = (self.ollama_url or "").strip().replace("\r\n", "\n").strip()
        if "\n" in u:
            u = u.splitlines()[0].strip()
        if not u:
            u = "http://127.0.0.1:11434"
        elif not u.startswith(("http://", "https://")):
            u = "http://" + u.lstrip("/")
        self.ollama_url = u
        self.llm_model = (self.llm_model or "").strip() or "qwen3:8b"

        if self.database_url:
            du = str(self.database_url).strip().replace("\r\n", "\n")
            if "\n" in du:
                du = du.splitlines()[0].strip()
            self.database_url = du or None

        if not self.pdf_paths:
            raw = os.environ.get("RAG_PDF_PATHS")
            if raw:
                resolved: list[Path] = []
                for p in raw.split(os.pathsep):
                    p = p.strip()
                    if not p:
                        continue
                    path = Path(p)
                    if not path.is_absolute():
                        path = self.project_root / path
                    resolved.append(path)
                self.pdf_paths = resolved
            else:
                lib = self.library_dir
                self.pdf_paths = [
                    lib / "ТКРФ.pdf",
                    lib / "ФЗ-209.pdf",
                    lib / "НКРФ.pdf",
                ]

    def manifest_path(self) -> Path:
        return self.library_dir / "manifest.json"

    def write_manifest(self, extra: dict) -> None:
        self.library_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "qdrant_mode": "http" if self.qdrant_url else "local_path",
            "qdrant_url": self.qdrant_url,
            "qdrant_local_path": str(self.qdrant_local_path) if self.qdrant_local_path else None,
            "postgres_enabled": bool(self.database_url),
            "source_files_in_postgres": self.source_files_in_postgres,
            "qdrant_collection": self.qdrant_collection,
            "embedding_model": self.embedding_model,
            "text_sanitizer_enabled": self.text_sanitizer_enabled,
            "knowledge_csv": str(self.knowledge_csv),
            "pdf_paths": [str(p) for p in self.pdf_paths],
            **extra,
        }
        self.manifest_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_settings() -> Settings:
    return Settings()
