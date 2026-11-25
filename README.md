# BSV Docs Assistant

A Retrieval-Augmented Generation (RAG) chatbot that answers BSV developer questions from a curated documentation knowledge base, with citations. It refuses to answer when the documents don't support one.

Stack: Python, Streamlit, OpenAI (embeddings + chat), ChromaDB.

## Pipeline

Document → Load → Clean → Chunk → Embed → Store → Query → Retrieve → Filter → Generate → Cite

### Load, clean, chunk (implemented: `src/loader.py`, `cleaner.py`, `chunker.py`)

- **Load:** `.txt` and `.pdf`. Text files carry `SOURCE`/`RETRIEVED`/`LICENSE` headers and `===== PAGE|FILE|SECTION: x =====` markers, which become sections so every chunk keeps its original page or file. A bad file (empty, corrupt, scanned PDF, header-only) is reported in an error list and skipped; the rest still load.
- **Clean:** strips GitBook/HTML tags, images, horizontal rules, front matter, HTML entities, and repeated in-page navigation lines. Code fences are kept verbatim. PDFs also lose repeated headers/footers and page numbers, and get hyphenated breaks rejoined and hard-wrapped lines reflowed.
- **Chunk:** about 1200 characters (about 300 tokens) with about 200 characters of overlap.
  - *Why this size:* the docs mix prose and API reference. Smaller chunks separate a method's description from its signature; larger ones blur several topics into one embedding.
  - *Splitting:* markdown headings (levels 1-3) first, then paragraphs. Code fences are atomic and split by line (re-fenced) only when one block alone exceeds the size.
  - *Overlap:* carried as whole trailing blocks, so a sentence or code fence is never cut mid-way. Heading boundaries get no overlap because they are already clean topic breaks.
  - *Guards:* a heading never ends a chunk, tiny fragments fold into the previous chunk, and chunk IDs are deterministic (`<file>_<section>_<chunk>`), so re-ingesting never duplicates embeddings.
  - *Metadata per chunk:* source file, source URL, section, heading, citation string, license, retrieved date, content hash, and page (PDFs).

Check it: `python -m src.ingest --sample 3` and `python -m pytest`.

### Embed, store (implemented: `src/embedder.py`, `src/store.py`)

- **Embed:** `text-embedding-3-small` via the OpenAI API, batched (100 chunks/request), embeds `chunk.embedding_text` (source + heading prefix) not the bare `chunk.text`. The SDK's built-in retry (`max_retries=5`) handles rate limits and transient network errors.
- **Store:** ChromaDB `PersistentClient` (`chroma_db/`), cosine distance space. Upsert by `chunk_id`; a chunk is skipped if its stored `content_hash` is unchanged, so re-running `python -m src.store` never re-embeds anything and the app never re-embeds on startup.
- Build/refresh the index: `python -m src.store` (`--dry-run` shows what would change with no API calls).

### Query, retrieve, filter (implemented: `src/retriever.py`)

- Query is embedded with the same model as the chunks, then `collection.query(n_results=K)`.
- **Similarity** = `1 - cosine distance`.

#### K experiment

Compared K=3, 5, 8 on real queries against the built index:

- **K=3** returns only strong matches but can be too narrow: on a multi-section query ("connect a wallet and then inscribe an ordinal") it returned three chunks all from the same file, missing the wallet-SDK side of the question entirely.
- **K=8** starts admitting `possible`-tier (weaker) matches on vague queries, e.g. "tell me about tokens" pulled in 6 possible-tier chunks alongside 2 strong ones — more noise for the generator to sift through.
- **K=5** is the chosen default: same practical coverage as K=3 on specific questions, catches one or two more angles on vague/multi-topic questions, without K=8's drop into weaker matches.
- **Known limitation:** K alone doesn't fix topic coverage. The wallet+inscribe query returned only ordinals-related chunks even at K=8 — the embedding model weighted "inscribe an ordinal" more heavily than "connect a wallet" in that phrasing, so no K value pulled in `bsv_ts_sdk_reference.txt`. Fixing that would mean query rewriting or multi-query retrieval, out of scope here.
- **Known limitation (ranking, not missing content):** a question asking specifically for the `ord://` recursive-inscription HTML example scored the correct chunk (`ordinals_protocol_spec.txt`, "Original inscription by Ordinal Number") around rank 10 at K=10 (similarity 0.536) — below several more-generic chunks that merely share keywords. The content exists and is correctly chunked and cited; this is a vocabulary-mismatch ranking miss (the chunk doesn't use the word "recursive," the query does), not an absent document. Before concluding content is missing, check what's actually indexed — adding a document here would have created a duplicate, which is exactly what happened on the first pass (caught and reverted; see `docs/SOURCES.md`).

#### Retrieval calibration

Measured against the real 1,401-chunk index with direct, paraphrased, misspelled, multi-section, vague, adjacent-but-uncovered, and irrelevant questions:

| Question type | Example | Top similarity |
|---|---|---|
| Direct | "what does WalletClient do in @bsv/sdk?" | 0.697 |
| Direct | "what does BRC-100 specify?" | 0.576 |
| Paraphrased | "describe what the WalletClient class is used for..." | 0.705 |
| Misspelled | "how do i creat a BSV-21 token" | 0.644 |
| Multi-section | "connect a wallet and then inscribe an ordinal" | 0.591 |
| Vague (in-domain) | "ordinals" / "tell me about tokens" | 0.456 - 0.532 |
| Adjacent, not covered | "set up a Lightning Network channel" | 0.339 |
| Adjacent, not covered | "capital of bitcoin mining difficulty adjustment" | 0.356 |
| Irrelevant | "What is the capital of France?" | 0.121 |
| Irrelevant | "write me a poem about autumn" | 0.175 |

There's a clean gap between in-domain questions (≥0.46) and genuinely irrelevant ones (≤0.18), with plausible-but-uncovered questions landing in between (0.34-0.36). Thresholds:

- **STRONG ≥ 0.5** — specific in-domain questions land here almost without exception.
- **POSSIBLE ≥ 0.35** — vague in-domain questions and plausible-but-uncovered questions; still sent to the generator, whose system prompt is relied on to admit insufficient context rather than guess.
- **WEAK ≥ 0.2** — excluded from generation (not "usable"), shown in the source viewer only.
- **< 0.2** — irrelevant; triggers the safe fallback.

Known edge case: a nonsense-but-keyword-heavy query can land in POSSIBLE territory (e.g. 0.356) even though it isn't really answerable — the system prompt's "admit when context is insufficient" instruction is the backstop here, not the similarity score alone.

### Generate, cite (implemented: `src/generator.py`)

- Chat model: `gpt-4o-mini`. Always sent context + question together, never the bare question.
- System prompt: answer only from context, admit when context is insufficient, cite the source per fact, stay in the BSV-docs-assistant role, and two domain caveats (GorillaPool `ordinals.gorillapool.io` API is legacy; BSV-20 may be superseded by BSV-21).
- No usable (strong/possible) match → returns the fixed safe-fallback string instead of calling the model.

### Chat interface (implemented: `app.py`)

Streamlit chat UI: title/purpose/knowledge-base description, `st.session_state` history, `st.chat_input`/`st.chat_message`, a "View Sources" expander per answer (citation, similarity, label, chunk ID, text preview), sidebar with K control and index/model info, spinners during retrieval/generation, and a retrieval/generation/total timing caption. Errors (missing key, empty index, retrieval/generation failures) are caught and shown as `st.error` messages instead of crashing.

Run: `streamlit run app.py`

Full 10-question test log, run against the live model: `tests/test_log.md`.

## Setup

```
pip install -r requirements.txt
```

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add your OpenAI key.

## Run

```
streamlit run app.py
```

## Knowledge base

Source documents live in `docs/`. See `docs/SOURCES.md` for URLs and retrieval dates.
