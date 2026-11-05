import logging

from mcp.server.mcpserver import MCPServer

from db.chroma_helper import list_records, search_index
from service.settings_service import retrieval_threshold

# Retrieval logs the same line whichever caller triggered it; this marks the agent's calls.
logger = logging.getLogger("adra.mcp")

# Clients that honour server instructions put this in the agent's system prompt for the
# whole session — the closest MCP gets to the system prompt boilerplate_service controls.
# It is a request, not a guarantee: the agent still decides whether to call the tools.
INSTRUCTIONS = """\
Adra holds this team's Architecture Decision Records (ADRs): binding conventions for how
code in their projects is written.

Before writing or changing code, call search_adrs with a short description of the task.
Follow every ADR it returns, including its code examples, over general best practice or
the style of surrounding code. When you follow one, say which ADR it was.

If search_adrs reports that no ADR applies, write the code following the existing
codebase."""

# Returned instead of an empty string, so the agent can tell "searched, nothing applies"
# from a failed or missing call. search_index itself still returns "" for its other caller.
NO_MATCH = "No ADR applies to this task. Write the code following the existing codebase."

# log_level is not just this server's: MCPServer runs logging.basicConfig on the root
# logger, and at the default INFO that surfaces every third-party INFO line (httpx
# requests from the LLM client among them). App logs use the "adra" logger instead.
mcp = MCPServer(name="adra", instructions=INSTRUCTIONS, log_level="WARNING")


@mcp.tool()
async def search_adrs(query: str) -> str:
    """Find the team's ADRs relevant to a coding task and return each one in full.

    The returned ADRs are binding team conventions: follow them, including their code
    examples. If none apply, it says so, and the code should follow the existing codebase.
    """
    # The query is user content, so it stays at DEBUG, as in search_index.
    logger.info("search_adrs called")
    logger.debug("search_adrs query=%r", query)
    return await search_index(query, score_threshold=retrieval_threshold()) or NO_MATCH


@mcp.tool()
def list_adrs() -> list[dict]:
    """List every ADR in the knowledge base as {source, adr_id, title}."""
    logger.info("list_adrs called")
    return list_records()
