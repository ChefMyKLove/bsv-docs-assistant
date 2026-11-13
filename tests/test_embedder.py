"""Tests for the embedding step: batching, key lookup, no real API calls."""
from __future__ import annotations

import pytest

from src.embedder import MissingAPIKeyError, embed_texts, estimate_tokens, get_api_key


class _FakeResponse:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.data = [_FakeItem(v) for v in vectors]


class _FakeItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def create(self, input: list[str], model: str) -> _FakeResponse:
        self.calls.append(list(input))
        return _FakeResponse([[float(len(text))] for text in input])


class _FakeClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddings()


def test_embed_texts_batches_and_preserves_order():
    client = _FakeClient()
    texts = [f"text-{i}" for i in range(5)]
    vectors = embed_texts(texts, client, batch_size=2)
    assert len(client.embeddings.calls) == 3  # batches of 2, 2, 1
    assert vectors == [[float(len(t))] for t in texts]


class _BrokenSecrets:
    """Stands in for st.secrets when no secrets.toml exists, so tests never read the real file."""

    def __contains__(self, key):
        raise FileNotFoundError("no secrets.toml")


def test_get_api_key_from_env(monkeypatch):
    monkeypatch.setattr("streamlit.secrets", _BrokenSecrets())
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    assert get_api_key() == "sk-test-123"


def test_get_api_key_missing_raises(monkeypatch):
    monkeypatch.setattr("streamlit.secrets", _BrokenSecrets())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError):
        get_api_key()


def test_estimate_tokens_scales_with_length():
    assert estimate_tokens("") >= 1
    assert estimate_tokens("a" * 400) > estimate_tokens("a" * 40)
