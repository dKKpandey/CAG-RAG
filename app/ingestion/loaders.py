import uuid
from pathlib import Path

from app.ingestion.chunking import build_splitter

_TEXT_SUFFIXES = {".md", ".txt"}


def load_directory(path: str) -> list[tuple[str, dict]]:
    results = []
    for p in sorted(Path(path).glob("**/*.*")):
        if p.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        results.append((p.read_text(encoding="utf-8"), {"source": p.name}))
    return results


def load_and_chunk_texts(
    texts: list[tuple[str, dict]], chunk_size: int, chunk_overlap: int
) -> tuple[list[str], list[str], list[dict]]:
    splitter = build_splitter(chunk_size, chunk_overlap)
    ids: list[str] = []
    chunks: list[str] = []
    metadatas: list[dict] = []

    for text, meta in texts:
        for piece in splitter.split_text(text):
            ids.append(str(uuid.uuid4()))
            chunks.append(piece)
            metadatas.append(meta)

    return ids, chunks, metadatas
