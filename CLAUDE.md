# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Adra makes a team's **Architecture Decision Records (ADRs)** available to coding agents (Claude Code, Cursor, Copilot) over **MCP**. Before writing code, the agent calls Adra's `search_adrs` tool, gets back the relevant ADRs in full, and follows them, so its code matches the team's documented conventions instead of generic best practice or the style of the surrounding file. Adra doesn't generate code; the agent does.

**Current focus is the MCP integration** ([#24](https://github.com/AT-LOW45/adra/issues/24)). The VS Code extension, which generated code itself, is **on hold**: it still works, but it isn't being developed or published. Don't put work into it unless asked.

`README.md` is a short overview that points to the docs site (`docs-site/`, published at https://at-low45.github.io/adra/) for setup and agent configuration; `CONTRIBUTING.md` has the project layout and retrieval design. This file covers the operational/architectural details needed to work in the code.

## Git & pull requests — ASK FIRST

**Never `git commit`, `git push`, open a pull request, or merge a pull request without the user's explicit confirmation — every time, for each action.** Editing files in the working tree and creating local branches are fine without asking; anything that writes to git history or the remote is gated. Prepare the change, then **stop and ask**.

Branching model is GitHub Flow — `main` is protected and changes land via PR (see [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming and conventions).

## Components

| Path         | Stack                                                | Role                                                                          |
|--------------|------------------------------------------------------|-------------------------------------------------------------------------------|
| `rag/`       | Python 3.13 · FastAPI · LangChain · ChromaDB · MCP   | Backend: indexes ADRs, retrieves them, serves MCP at `/mcp` and the REST API. |
| `ui/`        | Vue 3 · Vite · PrimeVue · Tailwind · TypeScript      | Knowledge-base manager (write/upload/edit/review/delete ADRs, drafts).        |
| `extension/` | TypeScript · VS Code API                             | **On hold.** VS Code extension that generates code via the backend.           |
| `docs-site/` | VitePress                                            | Documentation site, deployed to GitHub Pages.                                 |
| `docs/`      | Markdown                                             | `adr/` sample ADRs for seeding; `generation-coverage.md` (extension-era test log). |

`ui/` builds to `ui/dist`, which `rag/server.py` mounts at `/` via `StaticFiles`. So the KB UI, the REST API and MCP are all served from **one origin** (`:8000`).

## Commands

**Backend (`rag/`):** uses `uv` (not pip). Needs MinIO running first (`docker compose up -d` from the repo root).
```bash
cd rag
uv run python main.py     # uvicorn on 127.0.0.1:8000, reload enabled
uv run python scripts/calibrate_threshold.py   # tune the retrieval score_threshold
uv run python scripts/seed_adrs.py             # re-seed the KB from docs/adr
uv run --with pyright pyright                  # type check, exactly as CI runs it
```
`main.py` reads `HOST`, `PORT`, `RELOAD` from the environment (a container sets `HOST=0.0.0.0`, `RELOAD=false`); `LOG_LEVEL` sets the app log level. There is no Python test suite.

**Connect an agent to a running backend:**
```bash
claude mcp add --scope user --transport http adra http://localhost:8000/mcp
```
Then start a **new** session; servers added mid-session aren't loaded. Opening `/mcp` in a browser returns a JSON-RPC error (`Missing session ID`); that's expected.

**UI (`ui/`):**
```bash
cd ui
npm run dev          # Vite dev server on :5173 (CORS-allowed by the backend)
npm run build        # vue-tsc -b && vite build → ui/dist (what the backend serves)
```
Rebuild `ui/` after changing `ui/.env` (`VITE_API_ENDPOINT`). The backend serves the last `ui/dist` build, not the dev server.

**Extension (repo root; on hold):**
```bash
npm run compile      # tsc -p ./  → out/
npm run lint         # eslint extension
npm test             # compile + lint (pretest) then vscode-test on out/test/**/*.test.js
# Press F5 in VS Code to launch an Extension Development Host with the extension loaded.
```
Tests are Mocha via `@vscode/test-cli` (config in `.vscode-test.mjs`) and run against **compiled JS in `out/`**, so compile first.

**Docker / release:** the root `Dockerfile` builds the backend image (UI built in a Node stage, embedding model built into the image, CPU-only PyTorch). Publishing a GitHub Release pushes it to GHCR for amd64 and arm64 (`.github/workflows/release.yml`). The extension is no longer built or published on release. CI (`ci.yml`) runs Pyright, the UI build and the docs build on PRs; the extension is no longer checked.

## Backend architecture (`rag/`)

Layering is `router → service → db/storage`. Entry point is `server.py` (the `app`); `main.py` only runs uvicorn. **Run the backend from inside `rag/`**: imports are top-level (`from router import ...`, `from db.chroma_helper import ...`) and `../ui/dist` is resolved against the working directory. (`chroma_db` and `record_manager.db` are anchored to `rag/` in code, and can be moved with `CHROMA_DB_PATH` / `RECORD_MANAGER_PATH`.)

- **`router/mcp_tools.py`** is the MCP server: `MCPServer` from the `mcp` SDK, **v2**, where `FastMCP` was renamed `MCPServer` (`from mcp.server.mcpserver import MCPServer`). Tools: `search_adrs(query)` (wraps `search_index`, unchanged) and `list_adrs()` (wraps `list_records`). The `INSTRUCTIONS` string is sent to clients, which put it in the agent's system prompt. It's what tells agents to check ADRs and follow them over local style, so **editing it changes agent behaviour**: treat it as product behaviour, not as a comment.
- **How MCP is served** (`server.py`): streamable HTTP inside the FastAPI app, deliberately not stdio, so agents share the loaded embedding model and the single Chroma store. The MCP app's routes are **appended to `app.router.routes`** rather than mounted, because a mount only matches `/mcp/` and the redirect breaks clients that POST to `/mcp`. They must come **before** the catch-all `/` UI mount. The session manager runs in the FastAPI `lifespan`, because a mounted sub-app's lifespan never runs.
- **`db/chroma_helper.py`** is the retrieval core. `search_index()` scores candidate *chunks* but returns each relevant ADR **reassembled in full** (`_assemble_source` sorts chunks by `chunk_index`), so code examples inside an ADR are never split away from their heading. Tunables live in the `search_index` signature: `candidate_k`, `score_threshold`, `max_sources` (3). They stay server-side and aren't exposed to agents. `score_threshold` defaults to `SCORE_THRESHOLD`, read from `RETRIEVAL_THRESHOLD` (default **0.58**, calibrated so coding tasks no ADR covers, like "parse a CSV line", get nothing). A value saved via `PUT /settings` overrides it at runtime: `service/settings_service.py` resolves saved → env → 0.58, and **callers pass `score_threshold=retrieval_threshold()`**, because `db/` must not import from `service/`. Calibrate with `scripts/calibrate_threshold.py`, whose JUNK list must be **unrelated coding tasks**, not off-topic text. A query matching nothing returns `""`; `search_adrs` turns that into an explicit `NO_MATCH` message for the agent. Each ADR starts with its `# ADR-NNN:` heading, which is how agents cite it.
- **Embeddings**: `BAAI/bge-base-en-v1.5` (local HuggingFace), normalized + cosine, with an asymmetric query-instruction prefix. **768-dim — changing the model requires rebuilding the Chroma collection.**
- **Indexing** uses LangChain incremental indexing (`cleanup="incremental"`) keyed on `source`, backed by a SQLite record manager. Chunking is by markdown header (`#`/`##`/`###`, headers preserved). The record-manager `NAMESPACE` is still `chroma/patterngen` from before the rename. **Don't change it**, or every indexed document is orphaned.
- **`source` is the identity key** everywhere (vector store metadata, blob key, record-manager group). It is derived **server-side** from the document's H1 title (`generate_source` → `slugify`), never supplied by the client. `next_adr_id()` scans existing records for the next `ADR-NNN`. It is best-effort, not a reservation, so concurrent creates can collide.
- **Settings** (`service/settings_service.py`) are JSON files under `settings/` in the bucket, one per area, so bucket backups carry them and a file that fails to parse breaks only its own area. Each is read once and cached in memory, and saving refreshes the cache, so changes apply without a restart.
  - `settings/retrieval.json` holds `retrieval_threshold` (`GET`/`PUT /settings`; `null` resets it to the default). v0.2.0 saved it as `settings/settings.json`, which is still read while `retrieval.json` doesn't exist and is deleted on the next save.
  - `settings/adr_format.json` holds the team's ADR format as `{"sections": [{title, purpose, required}]}` (#2); no file means `DEFAULT_SECTIONS`. One format per instance. It drives the Create form and the quality review, not indexing or retrieval.
- **`storage/blob_storage.py`** persists raw ADR markdown, drafts (`drafts/`) and settings (`settings/`) to S3-compatible blob storage (boto3). ADR keys sit at the bucket root and never contain `/`, so **anything that lists the bucket to re-index ADRs (#17) must skip the `drafts/` and `settings/` prefixes**. The vector store holds chunks for retrieval; the blob holds the canonical original. Deletes must hit both. **The backend refuses to start** if `BLOB_*` is unset or the bucket is unreachable.
- **LLM** (`config/llm_config.py`): any OpenAI-compatible provider via `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`. The default is Groq with `openai/gpt-oss-120b`, and `GROQ_*` still works as a fallback. Temperature 0, instantiated at import, so a missing key fails at startup. Used by the ADR quality review (`service/review_service.py`) and the extension's `/boilerplate` endpoint; **MCP retrieval doesn't use it**.
- **Logging**: app code logs through the `adra` logger (`logging.getLogger("adra.<area>")`), configured in `server.py` with uvicorn's formatter and level from `LOG_LEVEL`. It's scoped rather than root so third-party INFO (httpx etc.) stays quiet. `MCPServer` is created with `log_level="WARNING"` for the same reason, since it runs `basicConfig` on root. `adra.mcp` marks agent tool calls; `adra.retrieval` logs kept and dropped ADRs with scores. Query text is user content, so it's logged **only at DEBUG**. Successful `/mcp` requests are filtered out of uvicorn's access log.

## UI architecture (`ui/`)

Vue 3 `<script setup>`, vue-router, PrimeVue components, Tailwind v4 (via `@tailwindcss/vite`). `@` aliases `ui/src`. Conventions:
- **`api-service.ts`** centralizes all backend calls (`knowledgeBaseService`). Add new endpoints here, not inline in components.
- **Routes** are named constants in `router/routes.ts`; **pages** in `pages/`, reusable logic in **composables** (`composables/`, e.g. `useCreateAdr`, `useZodValidation`), validation via **Zod schemas** in `schemas/`.
- Editing an existing ADR re-indexes under its **existing source** (`saveMarkdown`); creating derives a new source from the H1 (`createDocument`).

## Extension architecture (`extension/`, on hold)

`commands → service → config`. `main.ts` registers `adra.generateCode` and `adra.openKnowledgeBase`.
- **`generate-code`** sends `{query, language, selection_context, file_content}` to `POST /boilerplate/generate-boilerplate` and gets back `{edits: [{search, replace}]}` (`BoilerplateEdits` in `schema/boilerplate_schema.py`). `edit.service.ts` finds each `search` in the file and applies it. Imports are left out of the generated code and added afterwards from the language server's code actions (`constants/code-actions.ts`). Agents over MCP made this pipeline's two hard problems unnecessary: placing edits ([#7](https://github.com/AT-LOW45/adra/issues/7)) and resolving imports ([#23](https://github.com/AT-LOW45/adra/issues/23)).
- **`api-config.ts`** builds the axios client from the `adra.ragEndpoint` setting.

## Gotchas

- **`localhost` vs `127.0.0.1`.** `ui/.env`'s `VITE_API_ENDPOINT` is baked into `ui/dist`. If the UI is opened at the other hostname, every request is cross-origin and fails CORS. Open the UI at the same host the build points to.
- **MCP host check.** The SDK's DNS-rebinding protection only accepts `localhost`/`127.0.0.1` hosts. A backend behind a real hostname will reject `/mcp` until an allow list is added; that isn't configurable yet.
- **`claude mcp add` scope.** The default (local) scope is keyed on the exact folder path, and the terminal (`C:/…`) and VS Code (`c:/…`) spell it differently. Use `--scope user` when testing.
- **The local index can drift from the blob.** Each machine has its own Chroma store and MinIO volume, and nothing rebuilds the index from the blob yet ([#17](https://github.com/AT-LOW45/adra/issues/17)). Check what's actually indexed (`list_records`) before drawing conclusions from retrieval.
- **No shared type contract over HTTP.** When you change a REST request/response shape, update **both** the Pydantic schema in `rag/schema/` and its TS caller (`ui/src/api-service.ts`, or the extension).
- **No authentication** on REST or MCP. Keep the backend on a trusted network.
- CORS in `server.py` allows only the Vite dev ports (`:5173`/`:5174`) and `127.0.0.1:8000`. Production is same-origin.
- Roadmap and tasks live in **GitHub Issues** (`AT-LOW45/adra`); release notes go on GitHub Releases. (There was a `DEVLOG.md` engineering journal — retired in favour of Issues + git history; recover from git history if needed.)
