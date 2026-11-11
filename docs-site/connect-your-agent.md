# Connect your agent

Adra serves MCP over streamable HTTP at one endpoint:

```
http://localhost:8000/mcp
```

Any MCP client that supports HTTP servers can connect to it. Once connected, the agent
gets two tools:

| Tool | What it does |
|------|--------------|
| `search_adrs(query)` | Returns the ADRs relevant to a coding task, each in full. When none apply, it says so, and the agent writes code following the existing codebase. |
| `list_adrs()` | Lists every ADR in the knowledge base by ID and title. |

::: warning Tested clients
So far only **Claude Code** has been tested end to end. The Cursor and VS Code setups
below follow each client's documented MCP configuration but haven't been verified with
Adra yet. Testing is tracked in [#29](https://github.com/AT-LOW45/adra/issues/29).
:::

## Claude Code

```bash
claude mcp add --scope user --transport http adra http://localhost:8000/mcp
```

Start a new session and run `/mcp`. `adra` should be listed as connected, with two tools.

Use `--scope user`, which makes Adra available in every project. The default scope is
tied to the exact folder path, and a terminal (`C:\…`) and VS Code (`c:\…`) can spell
the same folder differently on Windows, so a server added from one may not show up in
the other.

## Cursor

Add to `.cursor/mcp.json` in your project, or `~/.cursor/mcp.json` for every project:

```json
{ "mcpServers": { "adra": { "url": "http://localhost:8000/mcp" } } }
```

## VS Code with GitHub Copilot

Add to `.vscode/mcp.json` in your project:

```json
{ "servers": { "adra": { "type": "http", "url": "http://localhost:8000/mcp" } } }
```

## Tell your agent to use Adra

Adra's MCP server already asks agents to check the ADRs before writing code, and clients
that honour server instructions put that in the agent's system prompt. Repeating it in
your project's own instructions file makes it considerably more reliable, and costs one
line.

Each agent reads a different file from the repository root:

| Agent | File |
|-------|------|
| Claude Code | `CLAUDE.md` |
| Codex | `AGENTS.md` |

Add this line to whichever applies:

```markdown
Before making or suggesting code changes, call the `adra` MCP server's `search_adrs` tool and follow the ADRs it returns.
```

Commit the file, and everyone on the team gets the same behaviour without configuring
anything themselves.

## Check that the agent used Adra

Tool calls appear in the agent's session, and Adra logs each one along with which ADRs it
returned and their scores:

```
INFO:     adra.mcp - search_adrs called
INFO:     adra.retrieval - kept=[api-error-handling 0.71] dropped=[] threshold=0.58
```

With Docker, follow the log with `docker compose logs -f adra`. Set `LOG_LEVEL=DEBUG` in
`.env` to log the agent's search text as well.

## What Adra can't do

Adra offers ADRs; it can't force an agent to follow them. The agent decides whether to
call `search_adrs` and how much weight to give the result. The server's instructions and
the line in your instructions file make it very likely, but it isn't guaranteed.
