# RAG Flask Service (PDF Retrieval) — SQLite FTS5 + PyMuPDF

This is a minimal internal "RAG-style" retrieval service for born-digital PDFs.

- Ingest PDFs from a directory (recursive) or explicit file list
- Extract per-page text with PyMuPDF
- Chunk pages into 1–3 page snippets (configurable)
- Index chunks into SQLite FTS5 for ranked keyword search
- Query returns cited snippets (document + page range)

This is intentionally simple and service-free: no vector DB, no embeddings, no external search engine.
You can add embeddings later without changing the ingest/query API shape.

---

## Requirements

- Python 3.10+ recommended
- Works on Windows and Unix
- SQLite must support FTS5 (bundled with most Python distributions)

---

## Quick start

### 1) Create and activate a virtual environment

Linux/Unix:
```bash
python -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

