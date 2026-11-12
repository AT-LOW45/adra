# Contributing to Adra

This guide covers **how** we work — branching, commits, and pull requests. For what
the project is and how the pieces fit together, see [`README.md`](README.md) and
[`CLAUDE.md`](CLAUDE.md).

## Project structure

| Path | Stack | Role |
|------|-------|------|
| `rag/` | Python · FastAPI · LangChain · ChromaDB · MCP | Backend: indexes ADRs, retrieves them, serves the MCP endpoint and the REST API |
| `ui/` | Vue 3 · Vite · PrimeVue · TypeScript | Knowledge-base manager: write, upload, edit, review and delete ADRs |
| `docs-site/` | VitePress | Documentation site, deployed to GitHub Pages on every change to `main` |
| `docs/adr/` | Markdown | Sample ADRs used to seed the knowledge base |
| `extension/` | TypeScript · VS Code API | VS Code extension. **On hold**, not developed or published |

The Vue app is built to `ui/dist` and served by FastAPI at `/`, and MCP is served at
`/mcp`, so one server provides the knowledge-base UI, the REST API and MCP. To run it
locally, follow [Run from source](https://at-low45.github.io/adra/run-from-source).

### Retrieval

- **Embeddings:** `BAAI/bge-base-en-v1.5`, run locally. Normalized, cosine distance,
  with a query-instruction prefix for asymmetric retrieval.
- **Chunking:** by markdown header (`#`/`##`/`###`), one chunk per section, headers kept.
  Indexed incrementally into ChromaDB, with a SQLite record manager to skip unchanged
  chunks.
- **Ranking:** each ADR is scored by its best-matching chunk. ADRs above the threshold
  are kept, capped at 3, and each is returned in full, reassembled in document order.
  The threshold and cap are set on the server; agents can't change them.
- **MCP transport:** streamable HTTP, served from the same FastAPI app rather than a
  separate stdio process, so agents share the loaded embedding model and the one
  Chroma store.

## Branching model

We use **GitHub Flow** — simple and suited to a small team:

- **`main` is always stable and deployable.** Never commit directly to it.
- **Every change happens on a short-lived branch** off `main`, and lands via a pull
  request.
- **Keep branches small and focused** — one logical change per branch/PR.

```bash
git checkout main && git pull          # start from the latest main
git checkout -b feat/short-summary     # branch off
# ...make changes, commit...
git push -u origin feat/short-summary  # push and open a PR
# review → merge → delete the branch
```

## Branch naming

Name branches `<type>/<short-kebab-summary>`, where `<type>` matches the commit types
below:

| Type       | Use for                                    | Example                          |
|------------|--------------------------------------------|----------------------------------|
| `feat`     | a new feature                              | `feat/file-aware-edits`          |
| `fix`      | a bug fix                                  | `fix/cors-kb-ui`                 |
| `refactor` | restructuring without behavior change      | `refactor/rename-generate-code`  |
| `docs`     | documentation only                         | `docs/contributing`              |
| `chore`    | tooling, deps, cleanup                     | `chore/remove-unused-commands`   |
| `test`     | tests only                                 | `test/edit-service`              |
| `spike`    | throwaway experiments (never merged as-is) | `spike/lsp-symbols`              |

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/): a
`type: summary` subject in the imperative mood, with the same types as above.

```
feat: apply each edit to all occurrences (duplicate-anchor handling)
fix: strip stray control character in edit.service.ts
```

- Keep commits focused; prefer several small, coherent commits over one large one.
- Explain the *why* in the body when it isn't obvious from the diff.

## Pull requests

1. Open the PR against `main` with a clear title (same `type: summary` style) and a
   short description of what and why.
2. Make sure the relevant checks pass locally (see below). CI runs Pyright on the
   backend, the UI build and the docs build on every PR, and they must be green
   before merging.
3. **Squash and merge** by default, so `main` stays one clean commit per PR. Use a
   merge commit only when a branch's individual commits are worth preserving.
4. **Delete the branch** after merging.

## Running checks locally

Run the checks for whatever you touched. Full commands are in [`CLAUDE.md`](CLAUDE.md).

- **Backend (`rag/`):** `uv run --with pyright pyright`, exactly as CI runs it
- **KB UI (`ui/`):** `npm run build` (runs `vue-tsc`)
- **Docs site (`docs-site/`):** `npm run docs:build`, which also fails on dead links
- **Extension (on hold):** `npm run compile` · `npm run lint` · `npm test` from the repo root

## Releases

Publishing a GitHub Release builds the backend Docker image and pushes it to GHCR
(`ghcr.io/at-low45/adra`) for amd64 and arm64, tagged with the release version. Write
the release notes on the release itself.

When you change a request/response shape, update **both** sides — the Python
Pydantic schema and the TypeScript caller (there is no shared type contract).
