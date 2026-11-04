# Adra

**Ground the coding agent you already use in your team's architectural decisions.**

Adra makes your team's **Architecture Decision Records (ADRs)** available to coding agents such as Claude Code, Cursor and GitHub Copilot over the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Before the agent writes code, it asks Adra which ADRs apply and gets them back in full, so the code follows your team's conventions for error handling, response shapes, data fetching and whatever else you've documented, not generic best practice or whatever the surrounding file happens to do.

Adra doesn't generate the code. Your agent does that already, along with editing files and writing imports. Adra provides what the agent can't find out on its own: which of your team's decisions apply to this task.

## How it works

```
Coding agent (Claude Code, Cursor, Copilot, …)
        │  MCP: search_adrs("add an endpoint to list zones")
        ▼
Adra backend  ──►  retrieve relevant ADRs (ChromaDB vector search)
        │                     │
        │  ◄──────────────────┘  full ADRs, in document order
        ▼
Agent writes the code, following the ADRs it was given
```

- **Whole-ADR retrieval.** Rather than returning scattered chunks, Adra works out which *whole ADRs* are relevant and returns them in full, so the code examples in an ADR are never separated from the rule they illustrate. A request no ADR covers returns nothing, and the agent writes code normally.
- **The agent is told the ADRs are binding.** Adra's MCP server sends instructions that compatible clients put into the agent's system prompt: check the ADRs before writing code, and follow them over local style. This is a strong request, not a guarantee; see [Known limitations](#known-limitations).
- **A knowledge-base UI** for writing, uploading, editing and reviewing ADRs, served by the same backend.

## Project structure

| Path | Stack | Role |
|------|-------|------|
| `rag/` | Python · FastAPI · LangChain · ChromaDB · MCP | Backend: indexes ADRs, retrieves them, serves the MCP endpoint and the REST API |
| `ui/` | Vue 3 · Vite · PrimeVue · TypeScript | Knowledge-base manager: write, upload, edit, review and delete ADRs |
| `extension/` | TypeScript · VS Code API | VS Code extension. **On hold**; see [VS Code extension](#vs-code-extension-on-hold) |
| `docs-site/` | VitePress | Documentation site (deployed to GitHub Pages) |
| `docs/adr/` | Markdown | Sample ADRs used to seed the knowledge base |

The Vue app is built to `ui/dist` and served by FastAPI at `/`, and the MCP endpoint is served at `/mcp`, so one server provides all three: the knowledge-base UI, the REST API and MCP.

## Documentation

The documentation site is built with VitePress from `docs-site/` and deployed to **GitHub Pages** on every change (see [`.github/workflows/deploy-docs.yml`](.github/workflows/deploy-docs.yml)):

**https://at-low45.github.io/adra/**

## Prerequisites

- **Python ≥ 3.13** and [`uv`](https://docs.astral.sh/uv/)
- **Node.js** (for the Vue knowledge-base UI, and the docs site)
- An **LLM API key**, used by the knowledge base's ADR quality review. Retrieval over MCP doesn't call it, but the backend checks for the key at startup. Any OpenAI-compatible provider works — Groq (the default), OpenAI, OpenRouter, Together, DeepSeek — as does a local runtime such as [Ollama](https://ollama.com) or LM Studio, which keeps your ADRs off third-party infrastructure.

  > **The model must support tool calling / structured output.** The ADR quality review asks the model for a structured response rather than free text. A model without that support fails at call time, not at startup — and small local models often lack it.
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
# LOG_LEVEL=INFO                                # optional — DEBUG also logs retrieval queries
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

The knowledge-base UI is now available at `http://localhost:8000`, and the MCP endpoint at `http://localhost:8000/mcp`.

### 5. Connect your coding agent

**Claude Code:**

```bash
claude mcp add --scope user --transport http adra http://localhost:8000/mcp
```

Start a new session and run `/mcp`: `adra` should be listed as connected, with two tools. Use `--scope user`. The default scope is tied to the exact folder path, and a terminal (`C:\…`) and VS Code (`c:\…`) can spell the same folder differently, so a server added from one may not show up in the other.

**Other MCP clients** connect to the same URL over streamable HTTP. For example, Cursor (`.cursor/mcp.json`):

```json
{ "mcpServers": { "adra": { "url": "http://localhost:8000/mcp" } } }
```

and VS Code with GitHub Copilot (`.vscode/mcp.json`):

```json
{ "servers": { "adra": { "type": "http", "url": "http://localhost:8000/mcp" } } }
```

So far only Claude Code has been tested end to end.

> Opening `/mcp` in a browser returns a JSON error such as `Missing session ID`. That's expected: the endpoint is for MCP clients, which open a session first.

## Usage

Ask your agent for code as usual. You don't need to mention Adra or ADRs. The agent sees Adra's tools and instructions and is expected to check the ADRs itself before writing code.

| MCP tool | What it does |
|---------|--------------|
| `search_adrs(query)` | Returns the ADRs relevant to a coding task, each in full. Returns an empty string when none apply. |
| `list_adrs()` | Lists every ADR in the knowledge base as `{source, adr_id, title}`. |

To make sure an agent checks the ADRs, add a line to your project's `CLAUDE.md` (or your agent's equivalent):

```markdown
Before writing or changing code, call the `adra` MCP server's `search_adrs` tool and follow the ADRs it returns.
```

**Checking whether the agent used Adra:** tool calls appear in the agent's session, and the backend logs each one:

```
INFO:     adra.mcp - search_adrs called
INFO:     adra.retrieval - kept=[fastapi-endpoint-conventions 0.71] dropped=[...] threshold=0.50
```

Set `LOG_LEVEL=DEBUG` to log the agent's search queries as well.

### Managing ADRs

Use the knowledge base UI to write ADRs from a template, upload markdown ADRs, edit them in place, review their quality, and delete them. ADRs are chunked by markdown header and indexed for retrieval. Each ADR is identified by a source key derived from its `# ` title, and editing an ADR re-indexes it under that same key, replacing the old chunks.

**Write ADRs for an agent to follow.** Agents follow ADRs closely, so be precise. A rule that differs from your existing code works, as long as the ADR says so explicitly; include a CORRECT and an INCORRECT example. Agents take file paths literally: an ADR that names `src/schemas/api_response.py` will get that exact file, even if that means restructuring a module.

## Retrieval details

- **Embeddings:** `BAAI/bge-base-en-v1.5` (HuggingFace, local) — normalized, cosine distance, with a query-instruction prefix for asymmetric retrieval
- **Vector store:** ChromaDB (persisted to `rag/chroma_db`)
- **Chunking:** `MarkdownHeaderTextSplitter` on `#`/`##`/`###`, headers preserved, one chunk per section
- **Dedup:** LangChain incremental indexing with a SQLite record manager
- **LLM** (ADR quality review): Groq `openai/gpt-oss-120b` by default — set `LLM_MODEL` to override, or point `LLM_BASE_URL` at another provider (see [llm_config.py](rag/config/llm_config.py))
- **Retrieval:** ranks whole ADRs by their best-matching chunk, keeps those above a relevance threshold (capped at 3), and returns each in full, reassembled in document order. The threshold and cap are fixed on the server; agents can't change them.
- **MCP transport:** streamable HTTP, served from the same FastAPI app rather than as a separate stdio process, so agents share the already-loaded embedding model and the single Chroma store.

## Known limitations

- **Adra can't force an agent to follow ADRs.** The agent decides whether to call `search_adrs` and how much weight to give the result. The server instructions and a `CLAUDE.md` line make it very likely, but it isn't guaranteed.
- **Local hosts only, for now.** The MCP endpoint's DNS-rebinding protection accepts only `localhost` / `127.0.0.1`. A backend deployed behind a real hostname needs that host added to an allow list, which isn't configurable yet.
- **No authentication.** Neither the MCP endpoint nor the REST API checks who is calling. Keep the backend on a trusted network.
- The relevance threshold (`0.5`) is calibrated against a small knowledge base and is currently loose: unrelated requests can retrieve an ADR. Revisit it as you add ADRs, using `rag/scripts/calibrate_threshold.py`.
- Retrieval still depends somewhat on phrasing. If quality degrades as the knowledge base grows, query enrichment (e.g. HyDE) or a hosted embedding model are the next levers.

## VS Code extension (on hold)

`extension/` contains a VS Code extension that generates code itself. It sends an instruction and the open file to the backend's `/boilerplate` endpoint, where an LLM writes ADR-grounded edits that the extension applies in place. **It is on hold.** It still works, and the backend endpoints it uses are unchanged, but it isn't being actively developed and isn't published.

Coding agents now cover what it did: they write code, place edits and resolve imports themselves. That made the extension's two hardest problems unnecessary, namely locating edits in a file it only partly sees ([#7](https://github.com/AT-LOW45/adra/issues/7)) and fixing up imports after generation ([#23](https://github.com/AT-LOW45/adra/issues/23)). It may come back for developers who don't use an agent.

To run it: open the repo in VS Code and press **F5** to launch an Extension Development Host. The `adra.ragEndpoint` setting points it at the backend (default `http://127.0.0.1:8000`).

## Contributing & development

- **Contributing guide:** [CONTRIBUTING.md](CONTRIBUTING.md) — branching model, branch naming, and PR conventions.
- **CI:** GitHub Actions runs Pyright (backend), the UI build, the docs build, and compile/lint for the on-hold extension on every pull request, plus CodeQL/Dependabot/secret scanning. `main` is protected — changes land via pull request.
- **Release:** publishing a GitHub Release builds the backend Docker image and pushes it to GHCR. The extension is no longer built or published on release.
- **Roadmap & tasks:** [GitHub Issues](https://github.com/AT-LOW45/adra/issues)
- [CHANGELOG.md](CHANGELOG.md) — user-facing release notes
