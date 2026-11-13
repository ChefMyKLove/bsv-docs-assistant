"""Tests for query embedding + search wiring and score classification. No real API calls."""
from __future__ import annotations

from src.retriever import Match, classify, retrieve, usable_matches


class _FakeEmbeddings:
    def create(self, input, model):
        class _Resp:
            data = [type("Item", (), {"embedding": [0.1, 0.2, 0.3]})()]

        return _Resp()


class _FakeClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddings()


class _FakeCollection:
    def __init__(self, distances: list[float]) -> None:
        self.distances = distances
        self.last_query_kwargs = None

    def query(self, **kwargs):
        self.last_query_kwargs = kwargs
        n = len(self.distances)
        return {
            "ids": [[f"c{i}" for i in range(n)]],
            "documents": [[f"text {i}" for i in range(n)]],
            "metadatas": [[{"source_file": f"f{i}.txt"} for i in range(n)]],
            "distances": [self.distances],
        }


def test_classify_boundaries():
    assert classify(0.5) == "strong"
    assert classify(0.35) == "possible"
    assert classify(0.2) == "weak"
    assert classify(0.0) == "irrelevant"


def test_retrieve_embeds_query_and_classifies_matches():
    collection = _FakeCollection(distances=[0.1, 0.7, 0.9])  # similarity 0.9, 0.3, 0.1
    matches = retrieve("how do I mint an ordinal", collection=collection, client=_FakeClient(), k=3)
    assert [m.label for m in matches] == ["strong", "weak", "irrelevant"]
    assert matches[0].chunk_id == "c0"
    assert collection.last_query_kwargs["query_embeddings"] == [[0.1, 0.2, 0.3]]
    assert collection.last_query_kwargs["n_results"] == 3


def test_usable_matches_filters_weak_and_irrelevant():
    matches = [
        Match("a", "t", {}, 0.9, "strong"),
        Match("b", "t", {}, 0.4, "possible"),
        Match("c", "t", {}, 0.1, "weak"),
        Match("d", "t", {}, 0.0, "irrelevant"),
    ]
    assert [m.chunk_id for m in usable_matches(matches)] == ["a", "b"]


def test_usable_matches_empty_when_nothing_qualifies():
    matches = [Match("a", "t", {}, 0.0, "irrelevant")]
    assert usable_matches(matches) == []
