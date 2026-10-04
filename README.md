# Adra

**RAG-based code generation and editing that enforces your team's architectural decisions.**

Adra is a VS Code extension that generates and edits code grounded in your own **Architecture Decision Records (ADRs)**. Instead of producing generic code, it retrieves the ADRs relevant to what you're building and instructs the LLM to follow them — so the code matches your team's conventions for error handling, data fetching, response shapes, and whatever else you've documented.

Given a natural-language instruction, Adra reads the file you're working in, works out *what* to change and *where*, and applies precise edits in place — following your ADRs and resolving imports for you.

## How it works

```
VS Code (Generate Code)
        │  instruction + language + whole file (+ optional selection)
        ▼
FastAPI backend  ──►  retrieve relevant ADRs (ChromaDB vector search)
        │                     │
        │  ◄──────────────────┘  full ADRs, in document order
        ▼
      LLM  ──►  targeted search/replace edits that follow the ADRs
        │
        ▼
VS Code applies the edits in place ──► editor auto-adds the imports
```

Two ideas make this work:

- **Whole-ADR retrieval.** Rather than returning scattered chunks, Adra identifies which *whole ADRs* are relevant to your request and feeds them to the LLM in full — so the concrete code examples in an ADR are never dropped. Irrelevant requests retrieve nothing, so the model just generates normally instead of being misled.
- **File-aware edits.** The model doesn't emit a blob to paste at your cursor. It returns a set of `{search, replace}` edits; the extension locates each `search` in your file — tolerant of whitespace and trivial formatting differences — and applies the replacement in place. So a single instruction can span multiple regions (a function *and* its callers), and a rename updates every occurrence. Imports are deliberately left out of the model's output and resolved afterward by the editor's language server, so they always point at the correct paths.

## Project structure

| Path | Stack | Role |
|------|-------|------|
| `extension/` | TypeScript · VS Code API | The extension itself |
| `rag/` | Python · FastAPI · LangChain · ChromaDB | Backend: indexes ADRs, retrieves context, generates edits |
| `ui/` | Vue 3 · Vite · PrimeVue · TypeScript | Knowledge-base manager: upload, edit, delete ADRs |
| `docs-site/` | VitePress | Documentation site (deployed to GitHub Pages) |
| `docs/adr/` | Markdown | Sample ADRs used to seed the knowledge base |

The Vue app is built to `ui/dist` and served by FastAPI at `/`, so the backend and knowledge-base UI run as a single server.

## Documentation

The documentation site is built with VitePress from `docs-site/` and deployed to **GitHub Pages** on every change (see [`.github/workflows/deploy-docs.yml`](.github/workflows/deploy-docs.yml)):

**https://at-low45.github.io/adra/**

## Prerequisites

- **Python ≥ 3.13** and [`uv`](https://docs.astral.sh/uv/)
- **Node.js** (for the Vue knowledge-base UI, and the docs site)
- An **LLM API key**. Any OpenAI-compatible provider works — Groq (the default), OpenAI, OpenRouter, Together, DeepSeek — as does a local runtime such as [Ollama](https://ollama.com) or LM Studio, which keeps your ADRs off third-party infrastructure.

  > **The model must support tool calling / structured output.** Both the ADR quality review and code generation ask the model for a structured response rather than free text. A model without that support fails at call time, not at startup — and small local models often lack it.
- An **S3-compatible blob store** (for persisting raw ADR content) — for local development, use the bundled [MinIO](https://min.io/) setup, which only requires **Docker** (see step 2)

## Setup

### 1. Configure environment

Create a `.env` at the repo root:

```env
LLM_API_KEY=your_api_key
# LLM_BASE_URL=https://api.groq.com/openai/v1   # optional — defaults to Groq
# LLM_MODEL=openai/gpt-oss-120b                 # optional — default model
API_ENDPOINT=http://localhost:8000
BLOB_ENDPOINT=http://localhost:9000
BLOB_ACCESS_KEY=...
BLOB_SECRET_KEY=...
BLOB_BUCKET=adra-docs
```

> `GROQ_API_KEY` and `GROQ_MODEL` are still read as fallbacks, so an existing `.env` keeps working.

**Using a different provider** — set the base URL and model; the key is whatever that provider issues:

```env
# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# OpenRouter (proxies Anthropic, Gemini and others)
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-sonnet-4

# Local Ollama — nothing leaves your machine
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
```

> The `BLOB_*` values are also consumed by the bundled MinIO setup (step 2): `BLOB_ACCESS_KEY`/`BLOB_SECRET_KEY` become MinIO's root credentials and `BLOB_BUCKET` is the bucket it creates. Use `http://localhost:9000` for `BLOB_ENDPOINT` when running MinIO locally. If you point at a managed S3-compatible store instead, set these to that store's values and skip step 2. Note: MinIO requires the access key to be **≥ 3 characters** and the secret key **≥ 8 characters**, or the container won't start.

### 2. Start the blob storage (MinIO via Docker)

The repo includes a [docker-compose.yml](docker-compose.yml) that runs a local MinIO server and creates the `BLOB_BUCKET` on startup. It reads credentials and the bucket name from the repo-root `.env` (step 1), so no secrets are hardcoded.

```bash
docker compose up -d      # start MinIO and create the bucket (pulls images on first run)
```

- **S3 API:** `http://localhost:9000` (matches `BLOB_ENDPOINT`)
- **Web console:** `http://localhost:9001` — log in with `BLOB_ACCESS_KEY` / `BLOB_SECRET_KEY` to browse stored ADRs

Objects persist in the `minio-data` Docker volume across restarts. Other commands:

```bash
docker compose down       # stop (data is preserved)
docker compose down -v    # stop and delete all stored objects
```

Skip this step if you're using a managed S3-compatible store; just point the `BLOB_*` values in `.env` at it — **the bucket must already exist**, as Adra checks it is reachable but never creates it. (The MinIO setup above creates it for you; on S3, R2 or similar you create it yourself.)

> Blob storage is required, not optional — every ADR is stored there. The backend refuses to start if the `BLOB_*` values are missing, or if the bucket can't be reached, and says which. That is deliberate: left unchecked it would start, serve the UI and show an empty knowledge base, which reads as "no ADRs yet" rather than "storage was never set up".

### 3. Build the knowledge-base UI

```bash
cd ui
npm install
npm run build        # outputs to ui/dist, served by the backend
```

> `ui/.env` should set `VITE_API_ENDPOINT=http://localhost:8000` (same origin as the backend). Rebuild after changing it. For UI development with hot-reload, run `npm run dev` (Vite on :5173) instead.

### 4. Run the backend

```bash
cd rag
uv run python main.py    # FastAPI on http://localhost:8000 (reload enabled)
```

The knowledge-base UI is now available at `http://localhost:8000`.

### 5. Run the extension

Open the repo in VS Code and press **F5** to launch an Extension Development Host with Adra loaded.

## Usage

| Command | What it does |
|---------|--------------|
| **Adra: Generate Code** | Prompts for an instruction, sends the active file and its language to the backend, and applies the returned ADR-grounded edits **in place** — resolving imports automatically. If you have code selected, that selection is used as the focus for the change. |
| **Adra: Open Knowledge Base** | Opens the knowledge-base UI (the `ragEndpoint`) in your browser to manage ADRs. |

On activation the extension checks that the backend is reachable and warns if it isn't, so backend-dependent commands fail gracefully rather than silently.

### Managing ADRs

Use the knowledge base UI to upload markdown ADRs, edit them in-place, and delete them. ADRs are chunked by markdown header and indexed for retrieval. To replace an existing ADR, re-upload it with the **same source name** — indexing is incremental and will swap the old chunks for the new ones.

## Configuration

This extension contributes the following setting:

- `adra.ragEndpoint` — URL of the RAG backend. Default: `http://127.0.0.1:8000`.

## Retrieval details

- **Embeddings:** `BAAI/bge-base-en-v1.5` (HuggingFace, local) — normalized, cosine distance, with a query-instruction prefix for asymmetric retrieval
- **Vector store:** ChromaDB (persisted to `rag/chroma_db`)
- **Chunking:** `MarkdownHeaderTextSplitter` on `#`/`##`/`###`, headers preserved, one chunk per section
- **Dedup:** LangChain incremental indexing with a SQLite record manager
- **LLM:** Groq `openai/gpt-oss-120b` by default — set `GROQ_MODEL` to override, or swap the provider in [llm_config.py](rag/config/llm_config.py)
- **Retrieval:** ranks whole ADRs by their best-matching chunk, keeps those above a relevance threshold (capped), and returns each in full, reassembled in document order

## Known limitations

- The relevance threshold (`0.5`) is calibrated against a small knowledge base; revisit it as you add more ADRs, since a stronger embedding model compresses scores into a narrower band.
- Retrieval still depends somewhat on phrasing. If quality degrades as the knowledge base grows, query enrichment (e.g. HyDE) or a hosted embedding model are the next levers.
- File-aware edits rely on the model copying existing code accurately. Matching is tolerant of whitespace and trivial formatting differences, but a heavily paraphrased `search` block may not be located — when that happens the extension warns rather than editing the wrong place.

## Contributing & development

- **Contributing guide:** [CONTRIBUTING.md](CONTRIBUTING.md) — branching model, branch naming, and PR conventions.
- **CI:** GitHub Actions runs compile/lint (extension), build (UI), Pyright (backend), and the docs build on every pull request, plus CodeQL/Dependabot/secret scanning. `main` is protected — changes land via pull request.
- **Roadmap & tasks:** [GitHub Issues](https://github.com/AT-LOW45/adra/issues)
- [CHANGELOG.md](CHANGELOG.md) — user-facing release notes
