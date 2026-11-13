"""Generate an answer from the user's question plus retrieved context. Never the bare question.

The system prompt is the app's main safety mechanism: answer only from context,
admit when context is insufficient, stay in role, and cite sources so the reader
can tell the AI's explanation apart from the underlying source text.
"""
from __future__ import annotations

from .embedder import get_client
from .retriever import Match, SAFE_FALLBACK, usable_matches

CHAT_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are the BSV Dev Docs Assistant, a technical documentation assistant for \
Bitcoin SV (BSV) developers. You answer questions about @bsv/sdk, BRC standards, 1Sat Ordinals, \
the GorillaPool/1sat SDK, and sCrypt, using only the context chunks given to you below.

Rules:
- Answer only using the provided context. Never state a fact that isn't supported by it.
- If the context doesn't contain enough information to answer reliably, say so plainly instead of guessing.
- When you state a fact, reference which source supports it (by the citation given with that \
chunk), so the reader can tell your explanation apart from the underlying source text.
- Stay in role: a precise, helpful BSV developer docs assistant, not a general-purpose chatbot.
- Two domain caveats to apply when relevant: the GorillaPool `ordinals.gorillapool.io` API is \
legacy (new work uses 1sat-stack / @1sat/client); BSV-20 may be superseded by BSV-21 for new work."""


def build_context(matches: list[Match]) -> str:
    blocks = [f"[{m.metadata.get('citation', m.metadata.get('source_file'))}]\n{m.text}" for m in matches]
    return "\n\n---\n\n".join(blocks)


def generate_answer(question: str, matches: list[Match], client=None, model: str = CHAT_MODEL) -> str:
    """Answer from retrieved context + question; SAFE_FALLBACK if nothing usable was retrieved."""
    usable = usable_matches(matches)
    if not usable:
        return SAFE_FALLBACK
    client = get_client() if client is None else client
    context = build_context(usable)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    return response.choices[0].message.content
