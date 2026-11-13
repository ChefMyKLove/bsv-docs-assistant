"""Ingestion pipeline: load -> clean -> chunk.

Run from the project root:
    python -m src.ingest                 # summary of what would be indexed
    python -m src.ingest --sample 3      # also print 3 sample chunks
"""
from __future__ import annotations

import argparse
import logging
import statistics
from pathlib import Path

from .chunker import CHUNK_OVERLAP, CHUNK_SIZE, Chunk, chunk_document
from .cleaner import clean_document
from .loader import LoadError, load_documents

DEFAULT_DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def build_chunks(
    docs_dir: str | Path = DEFAULT_DOCS_DIR,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> tuple[list[Chunk], list[LoadError]]:
    """Load, clean and chunk every document. Per-file failures are returned, not raised."""
    docs, errors = load_documents(docs_dir)
    chunks: list[Chunk] = []
    for doc in docs:
        try:
            chunks.extend(chunk_document(clean_document(doc), size, overlap))
        except Exception as exc:
            errors.append(LoadError(doc.filename, f"processing failed: {type(exc).__name__}: {exc}"))
    return chunks, errors


def summarize(chunks: list[Chunk], errors: list[LoadError]) -> str:
    lines = [f"{len(chunks)} chunks from {len({c.metadata['source_file'] for c in chunks})} files"]
    if chunks:
        sizes = [c.metadata["char_count"] for c in chunks]
        lines.append(
            f"chars/chunk: min {min(sizes)}, median {int(statistics.median(sizes))}, max {max(sizes)}"
        )
        by_file: dict[str, int] = {}
        for c in chunks:
            by_file[c.metadata["source_file"]] = by_file.get(c.metadata["source_file"], 0) + 1
        lines += [f"  {n:5d}  {name}" for name, n in sorted(by_file.items())]
    for err in errors:
        lines.append(f"ERROR {err.filename}: {err.reason}")
    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default=str(DEFAULT_DOCS_DIR))
    parser.add_argument("--sample", type=int, default=0)
    args = parser.parse_args()
    built, errs = build_chunks(args.docs)
    print(summarize(built, errs))
    step = max(1, len(built) // max(args.sample, 1))
    for chunk in built[::step][: args.sample]:
        print("\n" + "=" * 70)
        print(chunk.chunk_id, "|", chunk.metadata["citation"])
        print("-" * 70)
        print(chunk.text)
