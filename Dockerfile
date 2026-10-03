# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — build the knowledge-base UI.
# rag/server.py serves ../ui/dist, and that directory is gitignored, so it has to
# be built here rather than copied in from the repo.
# ---------------------------------------------------------------------------
FROM node:22-slim AS ui

WORKDIR /ui
# Manifests first so a source edit doesn't invalidate the dependency layer.
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build


# ---------------------------------------------------------------------------
# Stage 2 — the backend.
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# The app runs from inside rag/: its imports are top-level ("from router import ...")
# and server.py mounts "../ui/dist", so the two must sit side by side under /app.
WORKDIR /app/rag

COPY rag/pyproject.toml rag/uv.lock ./
RUN uv sync --frozen --no-dev

COPY rag/ ./
COPY --from=ui /ui/dist /app/ui/dist

# 0.0.0.0, not the 127.0.0.1 default: binding to loopback inside a container means the
# published port refuses connections from the host. Reload is a development convenience.
ENV HOST=0.0.0.0 \
    PORT=8000 \
    RELOAD=false

# Everything stateful lives under /data so a single volume covers it.
# The embedding model (~400 MB) is deliberately not baked into the image; it downloads
# on first use. Pointing the HuggingFace cache at /data means that happens once rather
# than every time the container is replaced.
ENV CHROMA_DB_PATH=/data/chroma \
    RECORD_MANAGER_PATH=/data/record_manager.db \
    HF_HOME=/data/huggingface
RUN mkdir -p /data
VOLUME /data

EXPOSE 8000

# Started through main.py so HOST/PORT/RELOAD keep a single source of truth.
CMD ["uv", "run", "--frozen", "python", "main.py"]
