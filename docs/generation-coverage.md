# Code generation coverage

What `Generate Code` has actually been verified to do, and where it's known to fall short.
Issues track the *work*; this file tracks the *state*. Update it whenever a case is tested.

Legend: ✅ verified · ⚠️ works but untested since last change · ❌ known broken · ❔ never tried

## Languages

| Language | ADR grounding | Imports | Import route | Notes |
|---|---|---|---|---|
| Python (FastAPI) | ✅ | ✅ | per-diagnostic quickfix (Pylance) | Pylance ranks candidates badly — offered `from uvicorn import logging` above `import logging` |
| Vue SFC (`<script setup lang="ts">`) | ✅ | ✅ | whole-file `source.addMissingImports` (Volar) | merges into an existing import statement rather than adding a line |
| TypeScript (plain `.ts`) | ❔ | ⚠️ | whole-file `source.addMissingImports` | worked before the classifier rewrite; not retested since |
| JavaScript | ❔ | ❔ | presumably as TS | |
| Go | ❔ | ❌ | — | imports sit inside `import ( … )`, so the inserted line has no keyword to match |

## How imports get added

Generated code omits imports by design, so the extension asks the language server and
**applies** the fix. Two routes, in order of preference:

1. **Whole-file** — `source.addMissingImports`. Requested by kind, so whatever comes back is
   correct by construction. TS/JS and Volar offer it. Must run **once**: re-running merges the
   same symbol in again.
2. **Per-diagnostic** — walk each error and inspect the offered quickfixes. Pylance only
   offers this. Candidates must be: a quickfix (not a refactor), touching only this file, a
   single-line insertion, and reading like an import statement. Best = shortest statement.

### Gotchas learned the hard way
- `itemResolveCount` must be passed, or `action.edit` comes back `undefined`.
- **Never match on action titles** — they're vendor-specific *and* localised. Pylance says
  `Add "import logging"` (quoted); Volar says `Add import from '…'`.
- Pylance's import fix carries **two** edits: the new import line *plus* a rewrite of the
  symbol on the error line. Don't require every edit to be an insertion.
- A stale diagnostic can re-offer a fix already applied → duplicate imports.
- Refactors also insert whole lines. "Generate get/set accessors" was applied 7 times before
  the quickfix-kind and single-line guards existed.

## Grounding cases tested

| Date | Repo | ADR | Prompt | Result |
|---|---|---|---|---|
| 2026-09-17 | bestway-backend (FastAPI) | ADR-006 layering + permissions | add an endpoint to list zones | ✅ 5/5 conventions; derived `zone:read` for a new entity rather than copying the example |
| 2026-09-18 | customer-frontend (Vue) | ADR-005 async feedback | load the payment list using `billingAPI` | ✅ used `invoke({ tryCall, errorCall })`; also wired the handler into `onMounted` |
| 2026-09-18 | customer-frontend (Vue) | ADR-005 async feedback | resend the reset email with feedback | ✅ followed the ADR even though the surrounding file hand-rolls `try/catch` — grounding beat local style |

## Known gaps

- **Invents the repo's API surface.** Unless the prompt names the object, it guesses:
  produced `parentAPI.getBillingHistory()`, which doesn't exist (the real call is
  `billingAPI.getPayments()`). Generation sees the current file + retrieved ADRs, never the
  project's exports.
- **Reformats code outside the request** — dropped a trailing comma, changed brace style,
  collapsed a template paragraph. Edits should be minimal.
- **Whole-file context doesn't scale** — the entire file is sent, so a 2758-line file risks
  the 60s timeout.
- The per-diagnostic route can't handle a **merge-style** fix (rewriting an existing import
  line). Harmless while the whole-file route works; it's the fragile spot.

## Not yet tried

Plain `.ts` files since the rewrite · JavaScript · React/JSX · a Python repo with no venv ·
path aliases and monorepos · files with pre-existing errors unrelated to the generated code ·
languages whose imports aren't one-per-line (Go) · non-English VS Code display language
