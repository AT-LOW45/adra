import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.logging import DefaultFormatter
from router import boilerplate, knowledge_base, draft, system

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

app = FastAPI()

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
app.include_router(system.router)

app.mount("/", StaticFiles(directory="../ui/dist", html=True), name="ui")
