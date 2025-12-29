from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    db_path: Path
    default_docs_dir: Path

    max_chunk_chars: int
    min_chunk_chars: int
    max_pages_per_chunk: int

    default_top_k: int
    default_snippet_chars: int

    flask_host: str
    flask_port: int


def load_settings() -> Settings:
    db_path = Path(os.getenv("RAG_DB_PATH", "./data/rag.sqlite3"))
    default_docs_dir = Path(os.getenv("RAG_DEFAULT_DOCS_DIR", "./docs"))

    return Settings(
        db_path=db_path,
        default_docs_dir=default_docs_dir,
        max_chunk_chars=_env_int("RAG_MAX_CHUNK_CHARS", 8000),
        min_chunk_chars=_env_int("RAG_MIN_CHUNK_CHARS", 1200),
        max_pages_per_chunk=_env_int("RAG_MAX_PAGES_PER_CHUNK", 3),
        default_top_k=_env_int("RAG_DEFAULT_TOP_K", 5),
        default_snippet_chars=_env_int("RAG_DEFAULT_SNIPPET_CHARS", 800),
        flask_host=os.getenv("FLASK_HOST", "127.0.0.1"),
        flask_port=_env_int("FLASK_PORT", 8000),
    )
