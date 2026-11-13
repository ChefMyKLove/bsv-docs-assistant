"""Embed chunk text with OpenAI. The same model and function embed user queries.

Run from the project root:
    python -m src.embedder                # dry run: count chunks, estimate tokens/cost
    python -m src.embedder --dry-run       # same, explicit
    python -m src.embedder --sample 5      # embed 5 chunks for real (costs a little)
    python -m src.embedder --all           # embed every chunk for real (costs a little more)
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from typing import Sequence

from .chunker import Chunk
from .ingest import build_chunks

log = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100
PRICE_PER_1M_TOKENS = 0.02  # text-embedding-3-small, USD; estimate only, check OpenAI pricing for the real number


class MissingAPIKeyError(RuntimeError):
    pass


def get_api_key() -> str:
    """OPENAI_API_KEY from .streamlit/secrets.toml, falling back to the environment for CLI use."""
    try:
        import streamlit as st

        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass  # no secrets.toml, or not running inside Streamlit
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise MissingAPIKeyError(
            "OPENAI_API_KEY not found in .streamlit/secrets.toml or the OPENAI_API_KEY environment variable."
        )
    return key


def get_client(api_key: str | None = None):
    from openai import OpenAI

    return OpenAI(api_key=api_key or get_api_key(), max_retries=5)


def estimate_tokens(text: str) -> int:
    """Rough ~4-chars-per-token estimate for a cost ballpark; not exact billing."""
    return max(1, len(text) // 4)


def embed_texts(
    texts: Sequence[str], client, model: str = EMBED_MODEL, batch_size: int = BATCH_SIZE
) -> list[list[float]]:
    """Embed texts in batches. The client retries rate limits and network errors on its own."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = list(texts[i : i + batch_size])
        response = client.embeddings.create(input=batch, model=model)
        vectors.extend(item.embedding for item in response.data)
    return vectors


def embed_chunks(
    chunks: Sequence[Chunk], client, model: str = EMBED_MODEL, batch_size: int = BATCH_SIZE
) -> list[list[float]]:
    """Embed chunk.embedding_text (source + heading prefix), not the bare chunk.text."""
    return embed_texts([c.embedding_text for c in chunks], client, model, batch_size)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="no-op; this is the default")
    parser.add_argument("--sample", type=int, default=0, help="embed N chunks for real")
    parser.add_argument("--all", action="store_true", help="embed every chunk for real")
    args = parser.parse_args()

    chunks, errors = build_chunks()
    for err in errors:
        print(f"ERROR {err.filename}: {err.reason}")

    total_tokens = sum(estimate_tokens(c.embedding_text) for c in chunks)
    cost = total_tokens / 1_000_000 * PRICE_PER_1M_TOKENS
    print(f"{len(chunks)} chunks, ~{total_tokens:,} tokens (rough estimate)")
    print(f"estimated cost at ${PRICE_PER_1M_TOKENS}/1M tokens: ${cost:.4f}")

    sample = chunks if args.all else chunks[: args.sample]
    if not sample:
        raise SystemExit(0)  # dry run (default): no API calls

    client = get_client()
    start = time.perf_counter()
    vectors = embed_chunks(sample, client)
    elapsed = time.perf_counter() - start
    print(f"embedded {len(vectors)} chunks in {elapsed:.2f}s, dim={len(vectors[0])}")
