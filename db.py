from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class SearchResult:
    doc_id: str
    filename: str
    path: str
    page_start: int
    page_end: int
    score: float
    snippet: str


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            mtime REAL NOT NULL,
            size_bytes INTEGER NOT NULL,
            indexed_at REAL NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            page_start INTEGER NOT NULL,
            page_end INTEGER NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );
        """
    )

    # FTS5 for chunks.text; store chunk_id + doc_id + pages as UNINDEXED metadata.
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id UNINDEXED,
            document_id UNINDEXED,
            filename UNINDEXED,
            path UNINDEXED,
            page_start UNINDEXED,
            page_end UNINDEXED,
            text,
            tokenize = 'unicode61'
        );
        """
    )

    # Helpful indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);")
    conn.commit()


def upsert_document(
    conn: sqlite3.Connection,
    *,
    doc_id: str,
    path: str,
    filename: str,
    sha256: str,
    mtime: float,
    size_bytes: int,
    indexed_at: float,
) -> None:
    conn.execute(
        """
        INSERT INTO documents (id, path, filename, sha256, mtime, size_bytes, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            path=excluded.path,
            filename=excluded.filename,
            sha256=excluded.sha256,
            mtime=excluded.mtime,
            size_bytes=excluded.size_bytes,
            indexed_at=excluded.indexed_at;
        """,
        (doc_id, path, filename, sha256, mtime, size_bytes, indexed_at),
    )


def get_document_by_path(conn: sqlite3.Connection, path: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM documents WHERE path = ? LIMIT 1;",
        (path,),
    ).fetchone()
    return dict(row) if row else None


def delete_document_chunks(conn: sqlite3.Connection, doc_id: str) -> None:
    # Remove from chunks and FTS
    conn.execute("DELETE FROM chunks WHERE document_id = ?;", (doc_id,))
    conn.execute("DELETE FROM chunks_fts WHERE document_id = ?;", (doc_id,))


def insert_chunks(
    conn: sqlite3.Connection,
    chunk_rows: Iterable[tuple[str, str, int, int, str]],
) -> None:
    conn.executemany(
        """
        INSERT INTO chunks (id, document_id, page_start, page_end, text)
        VALUES (?, ?, ?, ?, ?);
        """,
        chunk_rows,
    )


def insert_fts_rows(
    conn: sqlite3.Connection,
    fts_rows: Iterable[tuple[str, str, str, str, int, int, str]],
) -> None:
    conn.executemany(
        """
        INSERT INTO chunks_fts (chunk_id, document_id, filename, path, page_start, page_end, text)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        fts_rows,
    )


def list_documents(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, filename, path, sha256, mtime, size_bytes, indexed_at
        FROM documents
        ORDER BY indexed_at DESC
        LIMIT ?;
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def search_chunks(
    conn: sqlite3.Connection,
    query: str,
    top_k: int,
    snippet_chars: int,
) -> list[SearchResult]:
    # Use bm25() ranking from FTS5.
    # We also generate a snippet using snippet() function for readability.
    rows = conn.execute(
        """
        SELECT
            document_id,
            filename,
            path,
            page_start,
            page_end,
            bm25(chunks_fts) AS score,
            snippet(chunks_fts, 6, '[', ']', '…', ?) AS snippet
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
        ORDER BY score
        LIMIT ?;
        """,
        (max(10, snippet_chars), query, top_k),
    ).fetchall()

    results: list[SearchResult] = []
    for r in rows:
        # In FTS5, lower bm25 score is better.
        results.append(
            SearchResult(
                doc_id=str(r["document_id"]),
                filename=str(r["filename"]),
                path=str(r["path"]),
                page_start=int(r["page_start"]),
                page_end=int(r["page_end"]),
                score=float(r["score"]),
                snippet=str(r["snippet"]),
            )
        )
    return results
