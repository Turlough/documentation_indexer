from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

import fitz  # PyMuPDF

from utils import normalize_text, sha256_file, stable_doc_id


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    page_start: int
    page_end: int
    text: str


@dataclass(frozen=True)
class IndexedDocument:
    doc_id: str
    path: str
    filename: str
    sha256: str
    mtime: float
    size_bytes: int
    indexed_at: float
    chunks: list[Chunk]


def extract_pages_text(pdf_path: Path) -> list[str]:
    doc = fitz.open(str(pdf_path))
    pages: list[str] = []
    try:
        for i in range(doc.page_count):
            page = doc.load_page(i)
            # "text" uses internal layout. Good default for born-digital PDFs.
            txt = page.get_text("text") or ""
            pages.append(normalize_text(txt))
    finally:
        doc.close()
    return pages


def build_chunks(
    pages_text: list[str],
    *,
    doc_id: str,
    max_chunk_chars: int,
    min_chunk_chars: int,
    max_pages_per_chunk: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []

    buf: list[str] = []
    page_start = 1
    current_start = 1
    current_end = 1

    def flush():
        nonlocal buf, current_start, current_end
        if not buf:
            return
        text = normalize_text("\n".join(buf))
        if text:
            chunks.append(
                Chunk(
                    id=uuid.uuid4().hex,
                    doc_id=doc_id,
                    page_start=current_start,
                    page_end=current_end,
                    text=text,
                )
            )
        buf = []

    for idx, text in enumerate(pages_text, start=1):
        # Skip empty pages but keep page progression by ending chunks properly.
        if not text:
            continue

        if not buf:
            current_start = idx
            current_end = idx
            buf = [text]
            continue

        candidate = "\n".join(buf + [text])
        pages_in_chunk = (idx - current_start) + 1

        if len(candidate) <= max_chunk_chars and pages_in_chunk <= max_pages_per_chunk:
            buf.append(text)
            current_end = idx
        else:
            # Ensure we don't create tiny chunks when avoidable:
            # if current chunk is too small and we can append at least one page, do so.
            if len("\n".join(buf)) < min_chunk_chars and pages_in_chunk <= max_pages_per_chunk:
                buf.append(text)
                current_end = idx
            flush()
            # Start new chunk with this page
            current_start = idx
            current_end = idx
            buf = [text]

    flush()
    return chunks


def index_pdf(
    pdf_path: Path,
    *,
    max_chunk_chars: int,
    min_chunk_chars: int,
    max_pages_per_chunk: int,
) -> IndexedDocument:
    stat = pdf_path.stat()
    sha256 = sha256_file(pdf_path)
    doc_id = stable_doc_id(sha256)

    pages = extract_pages_text(pdf_path)
    chunks = build_chunks(
        pages,
        doc_id=doc_id,
        max_chunk_chars=max_chunk_chars,
        min_chunk_chars=min_chunk_chars,
        max_pages_per_chunk=max_pages_per_chunk,
    )

    return IndexedDocument(
        doc_id=doc_id,
        path=str(pdf_path.resolve()),
        filename=pdf_path.name,
        sha256=sha256,
        mtime=float(stat.st_mtime),
        size_bytes=int(stat.st_size),
        indexed_at=time.time(),
        chunks=chunks,
    )
