"""Tests for answer generation: safe fallback, and that context+question (never bare question) is sent."""
from __future__ import annotations

from src.generator import build_context, generate_answer
from src.retriever import SAFE_FALLBACK, Match


class _FakeChatCompletions:
    def __init__(self) -> None:
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs

        class _Msg:
            content = "the answer"

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeChatCompletions()


class _FakeClient:
    def __init__(self) -> None:
        self.chat = _FakeChat()


def _match(label: str) -> Match:
    return Match("c1", "ordinals are inscribed on satoshis", {"citation": "doc.txt — section"}, 0.9, label)


def test_generate_answer_returns_safe_fallback_with_no_usable_matches():
    client = _FakeClient()
    answer = generate_answer("what is X?", [_match("weak"), _match("irrelevant")], client=client)
    assert answer == SAFE_FALLBACK
    assert client.chat.completions.last_kwargs is None  # no API call made


def test_generate_answer_sends_context_and_question_not_bare_question():
    client = _FakeClient()
    matches = [_match("strong")]
    answer = generate_answer("how do I inscribe an ordinal?", matches, client=client)
    assert answer == "the answer"
    messages = client.chat.completions.last_kwargs["messages"]
    assert messages[0]["role"] == "system"
    user_content = messages[1]["content"]
    assert "how do I inscribe an ordinal?" in user_content
    assert "ordinals are inscribed on satoshis" in user_content  # retrieved context present too


def test_build_context_includes_citation_and_joins_multiple_matches():
    matches = [_match("strong"), _match("possible")]
    context = build_context(matches)
    assert context.count("doc.txt — section") == 2
    assert "---" in context
