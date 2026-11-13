"""Tests for the persistent vector store: dedup logic and dry-run, no real embedding calls."""
from __future__ import annotations

from src.chunker import Chunk
from src.store import build_index, chunks_to_upsert, get_collection, similarity_from_distance


class _FakeCollection:
    def __init__(self, stored: dict[str, str]) -> None:
        self.stored = stored  # chunk_id -> content_hash

    def get(self, ids, include):
        found = [i for i in ids if i in self.stored]
        return {"ids": found, "metadatas": [{"content_hash": self.stored[i]} for i in found]}


def _chunk(chunk_id: str, content_hash: str) -> Chunk:
    return Chunk(chunk_id, "text", {"content_hash": content_hash})


def test_chunks_to_upsert_skips_unchanged():
    collection = _FakeCollection({"a": "hash1", "b": "hash2"})
    chunks = [_chunk("a", "hash1"), _chunk("b", "hash2-changed"), _chunk("c", "hash3")]
    result = chunks_to_upsert(collection, chunks)
    assert [c.chunk_id for c in result] == ["b", "c"]


def test_chunks_to_upsert_empty_input():
    assert chunks_to_upsert(_FakeCollection({}), []) == []


def test_similarity_from_distance():
    assert similarity_from_distance(0.0) == 1.0
    assert similarity_from_distance(1.0) == 0.0


def test_build_index_dry_run_makes_no_api_calls(tmp_path, monkeypatch):
    fake_chunks = [_chunk("x_000_000", "h1"), _chunk("x_000_001", "h2")]
    monkeypatch.setattr("src.store.build_chunks", lambda: (fake_chunks, []))

    def _fail_get_client():
        raise AssertionError("dry run must not create an OpenAI client")

    monkeypatch.setattr("src.store.get_client", _fail_get_client)

    result = build_index(tmp_path, dry_run=True)
    assert result == {"total": 2, "to_embed": 2, "errors": []}


def test_build_index_is_idempotent_on_unchanged_content(tmp_path, monkeypatch):
    fake_chunks = [_chunk("x_000_000", "h1")]
    monkeypatch.setattr("src.store.build_chunks", lambda: (fake_chunks, []))

    collection = get_collection(tmp_path)
    collection.upsert(ids=["x_000_000"], documents=["text"], metadatas=[{"content_hash": "h1"}], embeddings=[[0.1, 0.2]])

    def _fail_get_client():
        raise AssertionError("unchanged content must not be re-embedded")

    monkeypatch.setattr("src.store.get_client", _fail_get_client)

    result = build_index(tmp_path, dry_run=False)
    assert result == {"total": 1, "to_embed": 0, "errors": []}
