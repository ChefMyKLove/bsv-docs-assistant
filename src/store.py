"""Persistent Chroma vector store. Embed once, upsert by chunk_id, skip unchanged chunks.

Run from the project root:
    python -m src.store --dry-run   # show what would be embedded/stored; no API calls
    python -m src.store             # embed new/changed chunks for real and store them
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import chromadb

from .chunker import Chunk
from .embedder import embed_chunks, get_client
from .ingest import build_chunks

log = logging.getLogger(__name__)

CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_db"
COLLECTION_NAME = "bsv_docs"


def get_collection(path: str | Path = CHROMA_DIR):
    client = chromadb.PersistentClient(path=str(path))
    return client.get_or_create_collection(
        COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
    )


def similarity_from_distance(distance: float) -> float:
    """Chroma's cosine space returns a distance (0 = identical); similarity = 1 - distance."""
    return 1 - distance


def chunks_to_upsert(collection, chunks: list[Chunk]) -> list[Chunk]:
    """Chunks that are new or whose content_hash changed since the last upsert."""
    if not chunks:
        return []
    existing = collection.get(ids=[c.chunk_id for c in chunks], include=["metadatas"])
    stored_hash = {
        cid: meta.get("content_hash") for cid, meta in zip(existing["ids"], existing["metadatas"])
    }
    return [c for c in chunks if stored_hash.get(c.chunk_id) != c.metadata["content_hash"]]


def build_index(path: str | Path = CHROMA_DIR, dry_run: bool = False) -> dict:
    """Load/chunk everything, embed and upsert only what's new or changed."""
    collection = get_collection(path)
    chunks, errors = build_chunks()
    to_embed = chunks_to_upsert(collection, chunks)
    summary = {"total": len(chunks), "to_embed": len(to_embed), "errors": errors}
    if dry_run or not to_embed:
        return summary
    client = get_client()
    vectors = embed_chunks(to_embed, client)
    collection.upsert(
        ids=[c.chunk_id for c in to_embed],
        documents=[c.text for c in to_embed],
        metadatas=[c.metadata for c in to_embed],
        embeddings=vectors,
    )
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="show what would change; no API calls")
    parser.add_argument("--path", default=str(CHROMA_DIR))
    args = parser.parse_args()

    result = build_index(args.path, dry_run=args.dry_run)
    for err in result["errors"]:
        print(f"ERROR {err.filename}: {err.reason}")
    print(f"{result['total']} chunks total, {result['to_embed']} new or changed")
    print("dry run: nothing embedded or stored" if args.dry_run else f"stored in {args.path}")
