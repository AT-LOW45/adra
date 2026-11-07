import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.logging import DefaultFormatter
from router import boilerplate, knowledge_base, draft, settings, system
from router.mcp_tools import mcp

# App logs go through a dedicated "adra" logger rather than the root logger: configuring
# root at INFO would also surface every httpx request line from the LLM client and
# similar third-party chatter. Modules log via logging.getLogger("adra.<area>").
# Uvicorn's formatter keeps the output aligned with its own "INFO:     ..." lines.
_handler = logging.StreamHandler()
_handler.setFormatter(DefaultFormatter("%(levelprefix)s %(name)s - %(message)s"))
_logger = logging.getLogger("adra")
_logger.addHandler(_handler)
_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
_logger.propagate = False


def _not_mcp_success(record: logging.LogRecord) -> bool:
    """Drop uvicorn's access line for successful /mcp requests.

    Every MCP message (initialize, tools/list, each call, the stream) is its own request,
    so one agent session buries everything else. Failures are kept; tool calls are logged
    by adra.mcp instead. Args are (client, method, path, http_version, status).
    """
    args = record.args
    if not isinstance(args, tuple) or len(args) != 5:
        return True
    path, status = str(args[2]), args[4]
    return not (path.split("?")[0] == "/mcp" and isinstance(status, int) and status < 400)


logging.getLogger("uvicorn.access").addFilter(_not_mcp_success)

# MCP over streamable HTTP, served from this app rather than a separate stdio process, so
# agents share the already-loaded embedding model and the one Chroma store.
_mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # A mounted sub-app's own lifespan never runs, so start MCP's session manager here.
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(draft.router)
app.include_router(knowledge_base.router)
app.include_router(boilerplate.router)
app.include_router(settings.router)
app.include_router(system.router)
# Added as routes, not mounted at /mcp: a mount only matches "/mcp/", and the redirect from
# "/mcp" breaks clients that POST to the bare URL. Must come before the catch-all UI mount.
app.router.routes.extend(_mcp_app.routes)

app.mount("/", StaticFiles(directory="../ui/dist", html=True), name="ui")
