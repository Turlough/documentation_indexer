from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def stable_doc_id(sha256_hex: str) -> str:
    # A deterministic ID derived from content. Helps with versioning.
    # If the content changes, the ID changes.
    return sha256_hex


def normalize_text(s: str) -> str:
    # Light normalisation: collapse whitespace, preserve readability.
    s = s.replace("\u00a0", " ")
    s = " ".join(s.split())
    return s.strip()


def iter_pdf_paths(root: Path, recursive: bool = True) -> Iterable[Path]:
    if root.is_file():
        if root.suffix.lower() == ".pdf":
            yield root
        return

    if not root.exists():
        return

    pattern = "**/*.pdf" if recursive else "*.pdf"
    for p in root.glob(pattern):
        if p.is_file() and p.suffix.lower() == ".pdf":
            yield p
