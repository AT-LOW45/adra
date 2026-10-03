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

# The embedding model is baked in rather than fetched on first run. It is ~420 MB
# against an image that is already 5.4 GB, so the saving was never meaningful, while a
# runtime download meant every first start could fail — and it did: an interrupted fetch
# leaves a partial snapshot and surfaces as "Unrecognized processing class", which gives
# no hint of the real cause. Baking it also makes the image work with no outbound network
# at all, which matters for teams keeping their architecture decisions off the internet.
#
# It lives outside /data deliberately: the model is immutable and belongs to the image,
# whereas /data is the operator's volume. Keeping them apart avoids relying on Docker's
# copy-into-empty-volume behaviour.
ENV HF_HOME=/opt/huggingface
# Warmed by importing the module the app itself uses, so the cache holds exactly what it
# loads at runtime, at the revision pinned in chroma_helper.py. The data paths are sent
# to /tmp for this one step so the build does not write into the volume mountpoint.
RUN CHROMA_DB_PATH=/tmp/warm RECORD_MANAGER_PATH=/tmp/warm.db \
    .venv/bin/python -c "import db.chroma_helper" \
 && rm -rf /tmp/warm /tmp/warm.db

# Set AFTER the warm-up above, which needs the network. From here on the hub libraries
# must work from the baked cache alone: by default they still contact HuggingFace to
# revalidate even when a model is cached, which would reintroduce the runtime network
# dependency the baking was meant to remove — and make the image unusable offline.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# Stateful data lives under /data so a single volume covers it.
ENV CHROMA_DB_PATH=/data/chroma \
    RECORD_MANAGER_PATH=/data/record_manager.db
RUN mkdir -p /data
VOLUME /data

EXPOSE 8000

# Started through main.py so HOST/PORT/RELOAD keep a single source of truth.
CMD ["uv", "run", "--frozen", "python", "main.py"]
