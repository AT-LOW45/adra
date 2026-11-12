# Run from source

Run the backend and the knowledge base UI from a clone of the repository, to change Adra
itself or to try something before it's released. To just use Adra, the
[Quickstart](./getting-started) is quicker.

## What you need

- **Python 3.13 or later** and [uv](https://docs.astral.sh/uv/)
- **Node.js**, to build the knowledge base UI
- **Docker**, for the bundled MinIO storage, unless you use your own
  [S3-compatible bucket](#use-your-own-s3-bucket)
- **An API key for an OpenAI-compatible LLM**, used for ADR review
  ([choose a provider](#choose-an-llm-provider))

```bash
git clone https://github.com/AT-LOW45/adra.git
cd adra
```

## 1. Configure the environment

Create `.env` in the repository root:

```dotenv
LLM_API_KEY=your_llm_api_key
BLOB_ENDPOINT=http://localhost:9000
BLOB_ACCESS_KEY=adra
BLOB_SECRET_KEY=change-me-please
BLOB_BUCKET=adra-docs
# LOG_LEVEL=INFO             # DEBUG also logs the agent's search text
# RETRIEVAL_THRESHOLD=0.58   # minimum score for an ADR to be returned
```

The `BLOB_*` values also configure the bundled MinIO: the access and secret keys become
its credentials, and `BLOB_BUCKET` is the bucket it creates. MinIO needs an access key of
at least 3 characters and a secret key of at least 8, or it won't start.

## 2. Start the storage

```bash
docker compose up -d
```

This starts MinIO and creates the bucket. Its web console is at http://localhost:9001;
log in with `BLOB_ACCESS_KEY` and `BLOB_SECRET_KEY` to browse the stored ADRs. Data is
kept in a Docker volume across restarts. `docker compose down` stops MinIO, and
`docker compose down -v` also deletes everything stored.

## 3. Build the knowledge base UI

```bash
cd ui
npm install
npm run build
```

The build goes to `ui/dist`, which the backend serves.

::: tip Developing the UI
For hot reload, run `npm run dev` (Vite on port 5173) and set
`VITE_API_ENDPOINT=http://localhost:8000` in `ui/.env.development`. Keep it out of
`ui/.env`: a value there is baked into `npm run build`, and the UI then fails with CORS
errors whenever it's opened at a different hostname, such as `127.0.0.1` instead of
`localhost`. Without it, the built UI calls the backend on whatever address served it.
:::

## 4. Run the backend

```bash
cd rag
uv run python main.py
```

The backend must run from inside `rag/`. It reloads when you change Python files. The
knowledge base is at http://localhost:8000 and the MCP endpoint at
http://localhost:8000/mcp. [Connect your agent](./connect-your-agent) to it as usual.

The backend refuses to start if `LLM_API_KEY` is missing, if a `BLOB_*` value is
missing, or if the bucket can't be reached, and says which. Left unchecked, missing
storage would look like an empty knowledge base rather than a setup problem.

::: tip Windows: "An Application Control policy has blocked this file"
Windows' Smart App Control can refuse to load the compiled parts of Python packages
such as `grpcio`, even ones that loaded fine before. Run the backend in
[WSL](https://learn.microsoft.com/windows/wsl/install) instead, where Linux packages
aren't checked. With uv installed in WSL, from the repository root:

```bash
cd rag
UV_PROJECT_ENVIRONMENT=$HOME/.venvs/adra WATCHFILES_FORCE_POLLING=true uv run python main.py
```

`UV_PROJECT_ENVIRONMENT` keeps the Linux packages apart from the Windows `rag/.venv`,
and `WATCHFILES_FORCE_POLLING` makes reload notice files saved from Windows. Open the
knowledge base from Windows at http://localhost:8000 as usual. Don't run the Windows and
WSL backends at the same time, since both use the same index.
:::

## Choose an LLM provider

Adra uses an LLM only to review ADRs in the knowledge base. Agents searching ADRs over
MCP never call it. Any OpenAI-compatible provider works: set the base URL and model,
and use the key that provider issues.

```dotenv
# Groq (the default; these two lines can be left out)
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b

# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# OpenRouter, which proxies Anthropic, Gemini and others
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-sonnet-4

# Local Ollama, so nothing leaves your machine
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
```

The model must support structured output (tool calling), because the review asks for a
structured response. A model without it fails when a review runs, not at startup, and
small local models often lack it.

These settings work the same in the Docker [Quickstart](./getting-started): add them to
its `.env`. There, a local Ollama is at `http://host.docker.internal:11434/v1` rather
than `localhost`.

## Use your own S3 bucket

Point the `BLOB_*` values at any S3-compatible store, such as AWS S3 or Cloudflare R2,
and skip step 2. **Create the bucket first:** Adra checks that the bucket is reachable
but never creates it.
