from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from config import load_settings
from db import (
    connect,
    init_db,
    delete_document_chunks,
    get_document_by_path,
    insert_chunks,
    insert_fts_rows,
    list_documents,
    search_chunks,
    upsert_document,
)
from indexer import index_pdf
from utils import iter_pdf_paths

load_dotenv()

settings = load_settings()
app = Flask(__name__)

conn = connect(settings.db_path)
init_db(conn)


@app.get("/")
def root() -> Any:
    """API root endpoint with available routes."""
    return jsonify(
        {
            "name": "Documentation Indexer API",
            "version": "1.0.0",
            "endpoints": {
                "GET /health": "Health check endpoint",
                "GET /docs": "List indexed documents (query param: limit)",
                "POST /ingest": "Ingest PDF files for indexing",
                "POST /query": "Search the indexed documents",
            },
        }
    )


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.get("/docs")
def docs() -> Any:
    limit = int(request.args.get("limit", 200))
    return jsonify({"documents": list_documents(conn, limit=limit)})


@app.post("/ingest")
def ingest() -> Any:
    """
    Ingest PDFs.

    JSON body options:
    {
      "input_dir": "path/to/dir",     # optional
      "files": ["path/a.pdf", ...],   # optional
      "recursive": true,             # default true (only for input_dir)
      "force": false                 # default false (reindex even if unchanged)
    }
    """
    body = request.get_json(silent=True) or {}
    input_dir = body.get("input_dir")
    files = body.get("files")
    recursive = bool(body.get("recursive", True))
    force = bool(body.get("force", False))

    pdf_paths: list[Path] = []

    if files:
        for f in files:
            p = Path(f)
            if p.exists() and p.is_file() and p.suffix.lower() == ".pdf":
                pdf_paths.append(p)
    else:
        base = Path(input_dir) if input_dir else settings.default_docs_dir
        pdf_paths.extend(list(iter_pdf_paths(base, recursive=recursive)))

    indexed = 0
    skipped = 0
    errors: list[dict[str, str]] = []

    for pdf_path in pdf_paths:
        try:
            pdf_path_resolved = pdf_path.resolve()
            existing = get_document_by_path(conn, str(pdf_path_resolved))

            # Cheap change detection: mtime + size, and optionally sha.
            # We still compute sha during indexing; this check avoids work.
            if existing and not force:
                try:
                    stat = pdf_path_resolved.stat()
                    if float(existing["mtime"]) == float(stat.st_mtime) and int(existing["size_bytes"]) == int(stat.st_size):
                        skipped += 1
                        continue
                except Exception:
                    # If stat fails, just reindex
                    pass

            doc = index_pdf(
                pdf_path_resolved,
                max_chunk_chars=settings.max_chunk_chars,
                min_chunk_chars=settings.min_chunk_chars,
                max_pages_per_chunk=settings.max_pages_per_chunk,
            )

            # Replace existing doc entries with same path (and its chunks)
            if existing:
                delete_document_chunks(conn, str(existing["id"]))

            upsert_document(
                conn,
                doc_id=doc.doc_id,
                path=doc.path,
                filename=doc.filename,
                sha256=doc.sha256,
                mtime=doc.mtime,
                size_bytes=doc.size_bytes,
                indexed_at=doc.indexed_at,
            )

            chunk_rows = [(c.id, c.doc_id, c.page_start, c.page_end, c.text) for c in doc.chunks]
            insert_chunks(conn, chunk_rows)

            fts_rows = [(c.id, c.doc_id, doc.filename, doc.path, c.page_start, c.page_end, c.text) for c in doc.chunks]
            insert_fts_rows(conn, fts_rows)

            conn.commit()
            indexed += 1

        except Exception as e:
            conn.rollback()
            errors.append({"file": str(pdf_path), "error": str(e)})

    return jsonify(
        {
            "indexed": indexed,
            "skipped": skipped,
            "errors": errors,
            "db_path": str(settings.db_path),
        }
    )


@app.post("/query")
def query() -> Any:
    """
    Query the corpus.

    JSON:
    {
      "query": "your search terms",
      "top_k": 5,            # optional
      "snippet_chars": 800   # optional
    }
    """
    body = request.get_json(silent=True) or {}
    q = (body.get("query") or "").strip()
    if not q:
        return jsonify({"error": "Missing 'query'"}), 400

    top_k = int(body.get("top_k") or settings.default_top_k)
    snippet_chars = int(body.get("snippet_chars") or settings.default_snippet_chars)

    results = search_chunks(conn, q, top_k=top_k, snippet_chars=snippet_chars)

    payload = []
    for r in results:
        payload.append(
            {
                "doc_id": r.doc_id,
                "filename": r.filename,
                "path": r.path,
                "pages": list(range(r.page_start, r.page_end + 1)),
                "page_start": r.page_start,
                "page_end": r.page_end,
                "score": r.score,
                "snippet": r.snippet,
            }
        )

    return jsonify({"query": q, "top_k": top_k, "results": payload})


if __name__ == "__main__":
    # Dev server only. In production use gunicorn.
    app.run(host=settings.flask_host, port=settings.flask_port, debug=True)
