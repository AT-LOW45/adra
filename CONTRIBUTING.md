# Contributing to Adra

This guide covers **how** we work — branching, commits, and pull requests. For what
the project is and how the pieces fit together, see [`README.md`](README.md) and
[`CLAUDE.md`](CLAUDE.md).

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
2. Make sure the relevant checks pass locally (see below). Once CI is set up, PR
   checks must be green before merging.
3. **Squash and merge** by default, so `main` stays one clean commit per PR. Use a
   merge commit only when a branch's individual commits are worth preserving.
4. **Delete the branch** after merging.

## Running checks locally

Adra has three components — run the checks for whatever you touched. Full
commands are in [`CLAUDE.md`](CLAUDE.md).

- **Extension (`src/`, repo root):** `npm run compile` · `npm run lint` · `npm test`
- **Backend (`rag/`):** run with `uv`; type-check with Pyright (`pyproject.toml`)
- **KB UI (`ui/`):** `npm run build` (runs `vue-tsc`)

When you change a request/response shape, update **both** sides — the Python
Pydantic schema and the TypeScript caller (there is no shared type contract).
