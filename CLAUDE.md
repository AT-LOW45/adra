# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Adra is a VS Code extension that generates boilerplate grounded in a team's **Architecture Decision Records (ADRs)**. A RAG backend retrieves whole relevant ADRs and instructs an LLM to follow them, so generated code matches documented org conventions instead of being generic.

Read `README.md` for the product-level overview and retrieval design; this file covers the operational/architectural details needed to work in the code.

## Git & pull requests — ASK FIRST

**Never `git commit`, `git push`, open a pull request, or merge a pull request without the user's explicit confirmation — every time, for each action.** Editing files in the working tree and creating local branches are fine without asking; anything that writes to git history or the remote is gated. Prepare the change, then **stop and ask**.

Branching model is GitHub Flow — `main` is protected and changes land via PR (see [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming and conventions).

## Three components, one repo

| Path   | Stack                                          | Role                                                            |
|--------|------------------------------------------------|-----------------------------------------------------------------|
| `src/` | TypeScript · VS Code API                       | The extension. Registers commands, calls the backend over HTTP. |
| `rag/` | Python 3.13 · FastAPI · LangChain · ChromaDB   | Backend: indexes ADRs, retrieves context, generates code.       |
| `ui/`  | Vue 3 · Vite · PrimeVue · Tailwind · TypeScript | Knowledge-base manager (upload/edit/delete ADRs).               |

`ui/` builds to `ui/dist`, which `rag/server.py` mounts at `/` via `StaticFiles`. So the backend and the KB UI are served from **one origin** (`:8000`) in production; the extension's `adra.ragEndpoint` setting points at that same origin.

## Commands

**Extension (`src/`, repo root):**
```bash
npm run compile      # tsc -p ./  → out/
npm run lint         # eslint src
npm test             # compile + lint (pretest) then vscode-test on out/test/**/*.test.js
# Press F5 in VS Code to launch an Extension Development Host with the extension loaded.
```
Tests are Mocha via `@vscode/test-cli` (config in `.vscode-test.mjs`). To run a single test, filter with Mocha's `.only` in the test file, or `npx vscode-test --run out/test/<file>.test.js`. Note: tests run against **compiled JS in `out/`**, so compile first.

**Backend (`rag/`):** uses `uv` (not pip).
```bash
cd rag
uv run python main.py     # uvicorn on 127.0.0.1:8000, reload enabled
uv run python scripts/calibrate_threshold.py   # tune the retrieval score_threshold
```
Type checking is configured for Pyright (`[tool.pyright]` in `pyproject.toml`). There is no Python test suite.

**UI (`ui/`):**
```bash
cd ui
npm run dev          # Vite dev server on :5173 (CORS-allowed by the backend)
npm run build        # vue-tsc -b && vite build → ui/dist (what the backend serves)
```
Rebuild `ui/` after changing `ui/.env` (`VITE_API_ENDPOINT`). The backend must be rebuilt-aware: it serves the last `ui/dist` build, not the dev server.

## Backend architecture (`rag/`)

Layering is `router → service → db/storage`. Entry point is `server.py` (the `app`); `main.py` only runs uvicorn. **Run the backend from inside `rag/`** — imports are top-level (`from router import ...`, `from db.chroma_helper import ...`) and paths are relative to `rag/` (`./chroma_db`, `../ui/dist`).

- **`db/chroma_helper.py`** is the retrieval core. The distinctive design: `search_index()` scores candidate *chunks* but returns each relevant ADR **reassembled in full** (`_assemble_source` sorts chunks by `chunk_index`), so code examples inside an ADR are never split away from their heading. Tunables live in the `search_index` signature: `candidate_k`, `score_threshold` (0.5), `max_sources` (3). A query matching nothing returns `""` → the LLM generates normally.
- **Embeddings**: `BAAI/bge-base-en-v1.5` (local HuggingFace), normalized + cosine, with an asymmetric query-instruction prefix. **768-dim — changing the model requires rebuilding the Chroma collection** (`rag/chroma_db`).
- **Indexing** uses LangChain incremental indexing (`cleanup="incremental"`) keyed on `source`, backed by a SQLite record manager (`rag/record_manager.db`). Re-uploading with the **same source** swaps old chunks for new. Chunking is by markdown header (`#`/`##`/`###`, headers preserved).
- **`source` is the identity key** everywhere (vector store metadata, blob key, record-manager group). It is derived **server-side** from the document's H1 title (`generate_source` → `slugify`), never supplied by the client. `next_adr_id()` scans existing sources for the next `ADR-NNN` — it is best-effort, not a reservation, so concurrent creates can collide.
- **`storage/blob_storage.py`** persists raw ADR markdown to S3-compatible blob storage (boto3). The vector store holds chunks for retrieval; the blob holds the canonical original for editing. Deletes must hit both (see `knowledge_base.py` delete endpoints).
- **LLM** is Groq `llama-3.3-70b-versatile` (`config/llm_config.py`), temperature 0, instantiated at import — a missing `GROQ_API_KEY` fails fast at startup.

## Extension architecture (`src/`)

Layering mirrors the backend: `commands → service → config`. `extension.ts` registers three commands from `constants/commands.ts`; each command file is a default-exported handler.

- **`generate-boilerplate`**: capture the active editor *before* showing dialogs, prompt for intent, send `{query, language (editor.document.languageId), selection_context}` to `POST /boilerplate/generate-boilerplate`, insert the result at the cursor.
- **`wrap-in-try-catch`** is purely local text manipulation (no backend) — it re-indents the selection and wraps it.
- **`api-config.ts`** builds the axios client from the `adra.ragEndpoint` VS Code setting. The backend response shape is `{ code }` / `{ data, error }` style — match it when adding endpoints.

## UI architecture (`ui/`)

Vue 3 `<script setup>`, vue-router, PrimeVue components, Tailwind v4 (via `@tailwindcss/vite`). `@` aliases `ui/src`. Conventions:
- **`api-service.ts`** centralizes all backend calls (`knowledgeBaseService`). Add new endpoints here, not inline in components.
- **Routes** are named constants in `router/routes.ts`; **pages** in `pages/`, reusable logic in **composables** (`composables/`, e.g. `useCreateAdr`, `useZodValidation`), validation via **Zod schemas** in `schemas/`.
- Editing an existing ADR re-indexes under its **existing source** (`saveMarkdown`); creating derives a new source from the H1 (`createDocument`).

## Gotchas

- `src/rag/` contains only a stray `.venv` + `uv.lock` (a misplaced virtualenv) — **the real backend is `rag/`**. Don't edit or reference `src/rag/`.
- The extension talks to the backend over HTTP; there's no shared type contract. When you change a request/response shape, update **both** the Python `schema/boilerplate_schema.py` (Pydantic) and the TS caller.
- CORS in `server.py` only allows `:5173`/`:5174` (Vite dev). Production is same-origin, so no CORS needed there.
- Roadmap and tasks live in **GitHub Issues** (`AT-LOW45/adra`); `CHANGELOG.md` holds user-facing release notes. (There was a `DEVLOG.md` engineering journal — retired in favour of Issues + git history; recover from git history if needed.)
