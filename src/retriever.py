"""Embed the user's question, search the Chroma collection, classify match quality.

STRONG/POSSIBLE/WEAK were calibrated against the real 1401-chunk index with
direct, paraphrased, misspelled, multi-section, vague, adjacent-but-uncovered,
and irrelevant questions. Observed cosine similarity (1 - distance):
  - in-domain specific questions:      0.576 - 0.705
  - vague-but-in-domain questions:     0.456 - 0.532
  - adjacent/plausible-but-uncovered:  0.339 - 0.356
  - genuinely irrelevant questions:    0.102 - 0.175
See README.md "Retrieval calibration" for the full numbers and methodology.
"""
from __future__ import annotations

from dataclasses import dataclass

from .embedder import EMBED_MODEL, embed_texts, get_client
from .store import get_collection, similarity_from_distance

DEFAULT_K = 5

STRONG = 0.5
POSSIBLE = 0.35
WEAK = 0.2

SAFE_FALLBACK = (
    "I could not find enough relevant information in the provided documents "
    "to answer that question reliably."
)


@dataclass
class Match:
    chunk_id: str
    text: str
    metadata: dict
    similarity: float
    label: str  # "strong" | "possible" | "weak" | "irrelevant"


def classify(similarity: float) -> str:
    if similarity >= STRONG:
        return "strong"
    if similarity >= POSSIBLE:
        return "possible"
    if similarity >= WEAK:
        return "weak"
    return "irrelevant"


def retrieve(question: str, collection=None, client=None, k: int = DEFAULT_K) -> list[Match]:
    """Embed the question (same model as the chunks) and return the top-k matches."""
    collection = get_collection() if collection is None else collection
    client = get_client() if client is None else client
    [query_vector] = embed_texts([question], client, model=EMBED_MODEL)
    result = collection.query(
        query_embeddings=[query_vector],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    matches = []
    for chunk_id, text, meta, distance in zip(
        result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        similarity = similarity_from_distance(distance)
        matches.append(Match(chunk_id, text, meta, similarity, classify(similarity)))
    return matches


def usable_matches(matches: list[Match]) -> list[Match]:
    """Matches worth passing to the generator; empty means use SAFE_FALLBACK instead."""
    return [m for m in matches if m.label in ("strong", "possible")]
