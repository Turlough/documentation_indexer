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

### 1) .env
Copy env.example to .env.
Edit as necessary.

 Note in particular:
- RAG_DB_PATH
- RAG_DEFAULT_DOCS_DIR

### 2) Create and activate a virtual environment

Service will run on http://127.0.0.1:8000 by default.

Linux/Unix:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

### 3) Running
#### Run the service using 
```python app.py```

#### Check health: 
```bash curl http://127.0.0.1:8000/health```

#### Ingest a directory: 
``` bash
curl -X POST http://127.0.0.1:8000/ingest ^
  -H "Content-Type: application/json" ^
  -d "{\"input_dir\": \"./docs\", \"recursive\": true}"
```

#### Query:
```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"rotate logs", "top_k": 5}'
```
SQLite FTS5 supports:
- term queries: saml assertion
- phrase queries: "service account"
- boolean-ish ops: OR, NOT, and prefix log*

Examples:
- "application pool" OR apppool
- error NOT warning
- auth* (prefix)

#### List Documents:
```bash
curl http://127.0.0.1:8000/docs
```



