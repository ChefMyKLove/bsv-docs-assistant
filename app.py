"""BSV Dev Docs Assistant — a RAG chat UI over a fixed BSV developer documentation set.

Run: streamlit run app.py
"""
from __future__ import annotations

import time

import streamlit as st

from src.embedder import EMBED_MODEL, MissingAPIKeyError, get_client
from src.generator import CHAT_MODEL, generate_answer
from src.retriever import DEFAULT_K, Match, retrieve

st.set_page_config(page_title="BSV Dev Docs Assistant", page_icon="⛓️")


@st.cache_resource
def _collection():
    from src.store import get_collection

    return get_collection()


@st.cache_resource
def _client():
    return get_client()


def _index_size() -> int:
    try:
        return _collection().count()
    except Exception:
        return 0


@st.cache_resource
def _bootstrap_index():
    """Build the index once per running container if it's empty (e.g. first boot on a fresh deploy).

    Safe to call on every boot: content-hash dedup in build_index() means an
    already-populated index costs nothing and embeds nothing a second time.
    """
    from src.store import build_index

    return build_index()


def _render_sources(matches: list[Match]) -> None:
    usable = [m for m in matches if m.label in ("strong", "possible")]
    if not usable:
        st.caption("No sources met the relevance threshold.")
    for m in matches:
        citation = m.metadata.get("citation", m.metadata.get("source_file", m.chunk_id))
        st.markdown(f"**{citation}** — similarity {m.similarity:.2f} ({m.label}) — `{m.chunk_id}`")
        preview = m.text[:500] + ("…" if len(m.text) > 500 else "")
        st.text(preview)


st.title("BSV Dev Docs Assistant")
st.caption(
    "Answers Bitcoin SV developer questions from a fixed knowledge base: the @bsv/sdk reference, "
    "BRC standards, 1Sat Ordinals, the GorillaPool/1sat SDK, and sCrypt. It only answers from "
    "retrieved documentation and says so when it can't find reliable support for an answer."
)

try:
    _was_empty = _index_size() == 0
    spinner_msg = (
        "First-time setup: building the knowledge base index (one-time, ~$0.01)..."
        if _was_empty
        else "Syncing knowledge base with latest docs..."
    )
    with st.spinner(spinner_msg):
        _bootstrap_index()
except MissingAPIKeyError:
    st.error("OpenAI API key not configured. Add it in this app's Settings → Secrets and reboot.")
    st.stop()
except Exception as exc:
    st.error(f"Failed to build the knowledge base index: {type(exc).__name__}: {exc}")
    st.stop()

with st.sidebar:
    st.subheader("Settings")
    k = st.slider("Chunks to retrieve (K)", min_value=1, max_value=10, value=DEFAULT_K)
    st.divider()
    st.caption(f"Index size: {_index_size()} chunks")
    st.caption(f"Embedding model: {EMBED_MODEL}")
    st.caption(f"Chat model: {CHAT_MODEL}")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("matches"):
            with st.expander("View Sources"):
                _render_sources(message["matches"])

prompt = st.chat_input("Ask about @bsv/sdk, BRC standards, 1Sat Ordinals, or sCrypt...")

if prompt is not None:
    prompt = prompt.strip()
    if not prompt:
        st.warning("Please enter a question.")
        st.stop()

    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        try:
            if _index_size() == 0:
                raise RuntimeError(
                    "The knowledge base is empty. Run `python -m src.store` to build the index first."
                )

            t0 = time.perf_counter()
            with st.spinner("Searching the docs..."):
                matches = retrieve(prompt, collection=_collection(), client=_client(), k=k)
            t1 = time.perf_counter()
            with st.spinner("Writing an answer..."):
                answer = generate_answer(prompt, matches, client=_client())
            t2 = time.perf_counter()

            st.markdown(answer)
            with st.expander("View Sources"):
                _render_sources(matches)
            st.caption(f"retrieval {t1 - t0:.2f}s · generation {t2 - t1:.2f}s · total {t2 - t0:.2f}s")

            st.session_state.messages.append({"role": "assistant", "content": answer, "matches": matches})

        except MissingAPIKeyError:
            st.error("OpenAI API key not configured. Add it to `.streamlit/secrets.toml` and restart the app.")
        except RuntimeError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Something went wrong answering that question: {type(exc).__name__}: {exc}")
