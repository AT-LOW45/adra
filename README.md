# Adra

**Ground the coding agent you already use in your team's architectural decisions.**

Adra makes your team's **Architecture Decision Records (ADRs)** available to coding agents such as Claude Code, Cursor and GitHub Copilot over the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Before the agent writes code, it asks Adra which ADRs apply and gets them back in full, so the code follows your team's conventions, not generic best practice or whatever the surrounding file happens to do.

Adra doesn't generate the code. Your agent does that already. Adra provides what the agent can't find out on its own: which of your team's decisions apply to this task.

**📖 Documentation: https://at-low45.github.io/adra/**

## How it works

```
Coding agent (Claude Code, Cursor, Copilot, …)
        │  MCP: search_adrs("add an endpoint to list zones")
        ▼
Adra  ──►  finds the relevant ADRs and returns each one in full
        │
        ▼
Agent writes the code, following the ADRs it was given
```

- **Whole ADRs, not fragments.** Code examples are never separated from the rule they illustrate. A task no ADR covers gets nothing, and the agent writes code normally.
- **Agents are told the ADRs are binding.** Adra's server instructions ask the agent to check the ADRs before writing code and to follow them over local style.
- **A knowledge-base UI** for writing, uploading, reviewing and editing ADRs, and for testing which ADRs a task would find.

## Quickstart

You need Docker, an API key for an OpenAI-compatible LLM (used only to review ADRs), and an MCP-capable agent.

1. Save the `.env` and `docker-compose.yml` from the [Quickstart guide](https://at-low45.github.io/adra/getting-started), then run:

   ```bash
   docker compose up -d
   ```

2. Open http://localhost:8000 and add an ADR.

3. Connect your agent. For Claude Code:

   ```bash
   claude mcp add --scope user --transport http adra http://localhost:8000/mcp
   ```

4. Start a new session and ask for code as usual. You don't need to mention Adra.

## Documentation

| Guide | |
|-------|---|
| [Quickstart](https://at-low45.github.io/adra/getting-started) | Run Adra with Docker and connect Claude Code |
| [Connect your agent](https://at-low45.github.io/adra/connect-your-agent) | Cursor, VS Code + Copilot, and the instructions-file line that makes agents reliable |
| [Run from source](https://at-low45.github.io/adra/run-from-source) | Develop Adra, choose an LLM provider, use your own S3 bucket |

## Limitations

- **Adra can't force an agent to follow ADRs.** The agent decides whether to call `search_adrs` and how much weight to give the result. Server instructions and a line in your `CLAUDE.md` make it very likely, but not guaranteed.
- **Local use only, for now.** There's no authentication, and the MCP endpoint only accepts requests addressed to `localhost` or `127.0.0.1`. Keep Adra on your own machine or a trusted network.
- **Only Claude Code has been tested end to end.** Other clients are tracked in [#29](https://github.com/AT-LOW45/adra/issues/29).
- **The relevance threshold (0.58) was calibrated on a small knowledge base.** Check it against your own ADRs on the **Search Tuning** page, which can suggest and save a better value.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the project layout, how to run checks, and branch and PR conventions. Roadmap and tasks are in [GitHub Issues](https://github.com/AT-LOW45/adra/issues).

The `extension/` folder holds a VS Code extension that generated code itself. It's **on hold**: coding agents over MCP replaced it.

## License

[MIT](LICENSE)
