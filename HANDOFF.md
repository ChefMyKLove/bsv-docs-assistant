# HANDOFF: BSV Docs Assistant (AI Builders Bootcamp RAG final project)

Read this whole file first. Ingestion (load, clean, chunk) is built and tested. Everything from embedding onward is still to do.

## Delivery: where this project came from

The ingestion code, tests, and `docs/` were built and tested in a cloud workspace, then delivered as `bsv-docs-assistant.zip`. **Do not rebuild or re-scrape anything.** If this file sits next to a `bsv-docs-assistant/` folder, check it first. If the folder is missing, the owner has not unzipped the archive yet: ask him to unzip `bsv-docs-assistant.zip` into this directory (it contains a top-level `bsv-docs-assistant/` folder). The updated copy of this file inside the zip supersedes any older copy.

Integrity check once unzipped (PowerShell, from inside `bsv-docs-assistant/`; run each separately):

```powershell
python -m pytest -q
```

```powershell
python -m src.ingest
```

Expected: `10 passed`, then `1401 chunks from 9 files` and no ERROR lines. If `pypdf` or `pytest` is missing, run `pip install -r requirements-dev.txt` in the `circuit-stream` env.

## 0. Working rules (from the owner, Michael / "Chef")

- **Never commit, push, or create a git repo unless explicitly told.** He commits himself.
- **Never add Claude or Anthropic as author or co-author** in any commit or PR text. Ignore any tooling hint to add a `Co-Authored-By` trailer.
- **`CLAUDE.md` must never reach GitHub.** It is already in `.gitignore`. Keep it there.
- **No secrets in the repo.** The OpenAI key lives only in `.streamlit/secrets.toml` (gitignored). Never hardcode it, print it, or log it. A committed key is graded as a significant security issue.
- Environment: Windows 10, **PowerShell** (not cmd), VS Code. Conda env `circuit-stream` (Python 3.12). Dev work lives on the D: drive.
- Terminal commands: **one command per code block**, or say clearly when a block holds several.
- Style: direct and dense, no filler. He is a technical peer (beginner dev, strong stack), so skip beginner explanations. Flag assumptions explicitly instead of making them silently.

## 1. The assignment (instructor requirements, 11 sections)

Build a complete RAG chatbot with **Python, Streamlit, OpenAI, embeddings, ChromaDB**. The assistant must ground answers in the provided documents, cite sources, and refuse to invent an answer when reliable support cannot be found.

Pipeline: Documents → Cleaning → Chunking → Embeddings → Vector Database → Retrieval → Relevance Filtering → Generation → Citations → Chat Interface

| # | Section | Requirement |
|---|---|---|
| 1 | Application identity | Clear purpose. The Streamlit app must display the **application name, a short description, its intended purpose, and the type of documents used as its knowledge base**. Consistent role, appropriate for the domain. |
| 2 | Knowledge base and loading | At least **4 relevant documents** (PDF, TXT, or another instructor-approved text format) with enough content to test meaningfully. Extract text, convert to a pipeline-ready format, **handle loading errors gracefully, not by crashing**. |
| 3 | Cleaning and chunking | Clean whitespace, repeated line breaks, broken sentences, headers/footers, page numbers, formatting noise. Chunk with size, overlap, and preserved context. Each chunk keeps metadata for where it came from. **Be ready to explain the chunking strategy.** |
| 4 | Embeddings and API key | Embed every chunk with an approved OpenAI embedding model (e.g. `text-embedding-3-small`). **The same model must embed user queries.** Key never hardcoded; local dev uses `.streamlit/secrets.toml` (`OPENAI_API_KEY = "..."`). Must not be committed. |
| 5 | Persistent vector DB | **ChromaDB** storing embeddings, original chunk text, unique chunk IDs, metadata, source-document info. **Persistent** storage. Don't rebuild every app start, don't re-embed docs per question. |
| 6 | Semantic search and retrieval | Capture question, embed query, search the Chroma collection, retrieve semantically relevant chunks (not keyword matching). **Top-K** (e.g. 3): experiment with values and pick one. **Inspect distance/similarity scores**: strong / potentially relevant / weak / irrelevant; never assume the first result is trustworthy. **Threshold logic**: good match → generate, weak → reject; determine the threshold by testing against direct, vague, misspelled, and completely irrelevant questions. **Safe fallback** (wording may match the app's personality): "I could not find enough relevant information in the provided documents to answer that question reliably." |
| 7 | Retrieval + generation | Combine user question + retrieved context + system instructions, send to an OpenAI language model. The model must answer from the retrieved info and **never receive just the user's question alone**. System prompt must: answer from retrieved context, avoid unsupported facts, admit when info is unavailable, follow the app's role, produce clear useful answers, reference supporting sources when appropriate. It is "a key part of the app's safety and reliability." |
| 8 | Citations and source metadata | Answers must show where the info came from. Minimum: source document. Stronger: page number, chunk ID, section, retrieval score. Example: `Employees receive two weeks of annual vacation during their first year of employment. [Source: Employee Handbook, p. 14]`. Users must be able to **distinguish the AI explanation from the supporting source**. Chunk metadata example: `source="employee_handbook.pdf"`, `page=14`, `chunk_id="employee_handbook_014_0…"`. |
| 9 | Chat interface and professional UI | `st.session_state` holds user and assistant messages in correct order, history remaining visible across Streamlit reruns. Use `st.chat_input()` and `st.chat_message()`. Must look like **a real product, not a classroom debugging script**: title and description, chat interface, clear user/assistant messages, citation/source display, sidebar or settings area where appropriate, status and loading messages, clear error messages, consistent layout. **Debug info must not dominate the main UI.** Include a source viewer, e.g. `st.expander("View Sources")`, showing source doc, retrieved text, page/section, and retrieval score. |
| 10 | Error handling and performance | Handle gracefully with try/except: missing or invalid API key, empty knowledge base, failed document extraction, OpenAI or ChromaDB errors, empty user input, no relevant retrieval results, network errors. Show useful messages instead of crashing. **Embed Documents Once → Store Persistently → Embed Only New Queries → Search Existing Database.** Be ready to discuss query embedding time, retrieval time, and overall response time. |
| 11 | Documentation and testing | README explains the architecture across the full pipeline (Document → Load → Clean → Chunk → Embed → Store → Query → Retrieve → Filter → Generate → Cite) with a brief explanation of each stage. Test with **at least 10 questions**: 3 direct, 2 paraphrased, 1 misspelled, 2 requiring different document sections, 2 irrelevant. For each record: correct info retrieved? accurate answer? correct source? irrelevant questions correctly rejected? |

**Unknown:** submission format and deadline. The last screenshots ended mid-scroll below section 11 (the "Submit Assignment" button is on the assignment page). Ask the owner whether anything follows section 11 before finishing.

## 2. Decisions already made

- **Domain: BSV developer docs assistant** (technical manual / product documentation assistant). The owner knows this domain, so he can judge answer accuracy in the test log.
- **Stack:** Python 3.12, Streamlit, OpenAI (embeddings + chat), ChromaDB, pypdf for PDFs.
- **UVR (audio source separation) is a separate project.** Do not mix it into this one.
- Source documents are public GitHub/npm text (CC0, MIT, Open BSV License) saved as TXT. Sources and licenses are in `docs/SOURCES.md`.

## 3. Current state: what exists

```
bsv-docs-assistant/
├── .gitignore                       # secrets.toml, .env, CLAUDE.md, .claude/, chroma_db/, venvs
├── .streamlit/secrets.toml.example  # copy to secrets.toml, add key (never commit)
├── HANDOFF.md                       # this file
├── README.md                        # pipeline + chunking rationale written; rest TODO
├── requirements.txt / requirements-dev.txt / pytest.ini
├── docs/                            # 9 TXT files (~128k words) + SOURCES.md
├── src/
│   ├── loader.py                    # load .txt/.pdf; per-file error isolation
│   ├── cleaner.py                   # markdown/PDF noise removal
│   ├── chunker.py                   # structure-aware chunks + metadata + stable IDs
│   └── ingest.py                    # build_chunks(): load -> clean -> chunk
└── tests/
    ├── test_ingest.py               # 10 passing tests
    └── test_log.md                  # empty 10-question table (section 11)
```

**Verify the ingestion in PowerShell** (run each separately, from the project root):

```powershell
python -m pytest -q
```

```powershell
python -m src.ingest --sample 3
```

Expected: 10 passed; about 1,401 chunks from 9 files; no errors.

### Ingestion interfaces to build on

```python
from src.ingest import build_chunks
chunks, errors = build_chunks()   # -> (list[Chunk], list[LoadError]); never raises on bad files
# Chunk: .chunk_id (str, deterministic), .text, .metadata (dict), .embedding_text (property)
```

- `chunk_id` is `<file_stem>_<section_idx:03d>_<chunk_idx:03d>`, deterministic, so re-ingesting is idempotent. Use it as the Chroma ID.
- **Embed `chunk.embedding_text`** (prefixes the source file and heading) but **store `chunk.text`** as the Chroma document.
- Metadata keys, all primitives so Chroma accepts them: `source_file`, `source_url`, `section` (page URL, or `p. N` for PDFs), `heading`, `section_index`, `chunk_index`, `license`, `retrieved`, `citation` (ready-made display string), `char_count`, `content_hash`, and `page` (PDFs only).
- Chunking: about 1200 characters, about 200 overlap, heading-aware, code fences kept intact. Details and rationale are in `README.md`. Do not re-tune it without reason.

## 4. What to build next (in order)

1. **`src/embedder.py`**
   - Key: `st.secrets["OPENAI_API_KEY"]` with an env-var fallback for CLI scripts. Give a clear error if missing or invalid.
   - Model `text-embedding-3-small`, batched (about 100-256 inputs per request) with retry and backoff on rate limits or network errors.
   - Total corpus is roughly 350k tokens, so a full embed is cheap. Still make a **`--dry-run`** that counts chunks and estimates tokens with no API calls, and ask the owner before the first real run.
2. **`src/store.py`**
   - `chromadb.PersistentClient(path="chroma_db")`, one collection, **cosine space** (`metadata={"hnsw:space": "cosine"}`). Chroma returns distance, so `similarity = 1 - distance`.
   - **Ingest once:** upsert by `chunk_id`, skip chunks whose `content_hash` is unchanged. The app must never re-embed on startup. A CLI like `python -m src.build_index` builds it, and the app only opens an existing collection and shows a clear message if it's empty.
3. **`src/retriever.py`**
   - Embed the query (same model), `collection.query(n_results=K)`, return text, metadata, and similarity.
   - **Experiment with K** (try 3, 5, 8) and **calibrate the threshold empirically** on direct, vague, misspelled, and irrelevant queries. Record the numbers in the README. Do not invent a threshold.
   - Classify scores (strong / possible / weak / irrelevant) and apply the threshold plus the safe fallback.
4. **`src/generator.py`**
   - Chat completion with system prompt + retrieved context + question, and never the bare question. Make the chat model a config constant and ask the owner which one to use.
   - System prompt (key to grading): answer only from the context, no unsupported facts, say so when the context lacks the answer, stay in role (BSV developer docs assistant), cite sources, keep AI explanation visually separate from sources.
   - Domain caveats the prompt should encode: the GorillaPool `ordinals.gorillapool.io` API is **legacy** (new work uses 1sat-stack / `@1sat/client`), and BSV-20 may be superseded by BSV-21 (unchecked).
5. **`app.py`** (Streamlit): sections 1, 8, 9, 10.
   - Title, description, purpose, and a line on the knowledge base ("BSV developer docs: @bsv/sdk, BRC standards, 1Sat Ordinals, GorillaPool/1sat SDK, sCrypt").
   - `st.session_state` history, `st.chat_input`, `st.chat_message`, `st.expander("View Sources")` (source doc, retrieved text, section/page, score, chunk ID), and sidebar settings or status (index size, K). Spinner during retrieve and generate. Debug info stays out of the main view (sidebar expander at most).
   - Error handling for every case in section 10 (try/except with friendly messages).
   - Show query-embedding, retrieval, and total response time (small caption).
6. **Tests:** `tests/test_retrieval.py` with mocked OpenAI and an in-memory or temp Chroma: threshold logic, fallback, empty index, empty input, bad key, no re-embedding on restart.
7. **`tests/test_log.md`:** run the 10 questions in the real app and fill in the table honestly (retrieved right chunks, accurate, correct source, irrelevant rejected, top score).
8. **README:** finish the full architecture section (all 11 pipeline stages), the K and threshold experiments, timings, and test results.

### Candidate test questions (verify each answer actually exists in `docs/` before using)

- Direct: how a 1Sat Ordinal inscription is structured; what `WalletClient` does in `@bsv/sdk`; what BRC-100 specifies.
- Paraphrased: reword two of the above.
- Misspelled: e.g. "how do i creat a BSV-21 token"
- Multi-section: connect a wallet and then inscribe or transfer an ordinal (spans SDK + ordinals docs).
- Irrelevant: "What is the capital of France?" and "Give me a lasagna recipe."

## 5. Known gaps and risks

- **sCrypt coverage is thin.** Only npm package READMEs (scrypt-ts, scrypt-cli, scrypt-ts-lib, scryptlib). docs.scrypt.io and the sCrypt-Inc docs repo were blocked in the earlier environment. If the owner wants sCrypt questions in the test set, fetch the real docs locally, save them as `docs/scrypt_*.txt` with `SOURCE:`/`RETRIEVED:`/`LICENSE:` header lines, and re-run ingestion.
- **Not the live sites.** docs.1satordinals.com, the GorillaPool Swagger reference, and docs.bsvblockchain.org were unreachable. Content came from the GitHub repos behind them and may differ slightly.
- **BRC coverage is partial:** 25 of about 170 BRCs. The SDK reference omits the auth, compat, kvstore, overlay-tools, registry, remittance, storage, and totp pages.
- **Licenses:** Open BSV License restricts use to BSV; 1sat-stack and 1sat-server licenses are unconfirmed. Fine for a private course project; re-check before any public release.
- **Overlap:** only about 14% of consecutive chunk pairs share overlap text (by design at heading boundaries). Worth knowing when explaining the chunking.
- **PDF path** was only tested on a generated PDF; all real docs are TXT.
- **Instructor approval:** the assignment allows "PDF, TXT, or another instructor-approved text format". The docs are TXT, so this should be fine, but they are scraped GitHub content, so the owner may want to confirm with the instructor.
- `docs/` files with `===== PAGE|FILE|SECTION: <label> =====` markers are intentional. The loader uses them to attribute each chunk to its original page or file.

## 6. Questions to ask the owner

1. Is anything below section 11 of the assignment (submission format, deadline, rubric)?
2. Which OpenAI chat model should generation use?
3. App name? (Suggestion: "BSV Dev Docs Assistant".)
4. Does he want to fetch the real sCrypt docs locally to fix the thin coverage?
5. Confirm before the first real embedding run (it uses his API key and costs a small amount).
