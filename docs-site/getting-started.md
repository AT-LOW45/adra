# Quickstart

Run Adra with Docker, add an ADR, and connect Claude Code to it. It takes about ten
minutes, most of it the first image download, and you don't need to clone the repository.

## What you need

- **Docker**, with Docker Compose (included in Docker Desktop).
- **An API key for an OpenAI-compatible LLM.** Adra uses it only to review ADRs as you
  write them; agents searching your ADRs never call it. [Groq](https://console.groq.com)
  is the default and has a free tier. Other providers, including a local
  [Ollama](https://ollama.com), are covered in [Run from source](./run-from-source#choose-an-llm-provider).
- **A coding agent that supports MCP.** This guide uses
  [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). Other clients
  are covered in [Connect your agent](./connect-your-agent).

## 1. Create the configuration

Make an empty folder, for example `adra/`, and save these two files in it.

`.env`, with your own values:

```dotenv
LLM_API_KEY=your_llm_api_key

# Credentials for the bundled MinIO storage. Choose your own; the access key needs at
# least 3 characters and the secret key at least 8.
BLOB_ACCESS_KEY=adra
BLOB_SECRET_KEY=change-me-please
BLOB_BUCKET=adra-docs
```

`docker-compose.yml`, unchanged:

```yaml
# Adra and the S3-compatible storage it keeps ADRs in.
services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9001:9001" # storage web console; Adra reaches MinIO on the internal network
    environment:
      MINIO_ROOT_USER: ${BLOB_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${BLOB_SECRET_KEY}
    volumes:
      - minio-data:/data
    restart: unless-stopped

  # Runs once: waits for MinIO, then creates the bucket if it doesn't exist.
  createbucket:
    image: minio/mc:latest
    depends_on:
      - minio
    environment:
      BLOB_ACCESS_KEY: ${BLOB_ACCESS_KEY}
      BLOB_SECRET_KEY: ${BLOB_SECRET_KEY}
      BLOB_BUCKET: ${BLOB_BUCKET}
    entrypoint: >
      /bin/sh -c "
      until mc alias set local http://minio:9000 $${BLOB_ACCESS_KEY} $${BLOB_SECRET_KEY}; do
        echo 'waiting for minio...'; sleep 1;
      done;
      mc mb --ignore-existing local/$${BLOB_BUCKET};
      "

  adra:
    image: ghcr.io/at-low45/adra:0.2.0
    depends_on:
      createbucket:
        condition: service_completed_successfully
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      BLOB_ENDPOINT: http://minio:9000
    volumes:
      - adra-data:/data # the search index
    restart: unless-stopped

volumes:
  minio-data:
  adra-data:
```

## 2. Start Adra

```bash
docker compose up -d
```

The first run downloads the Adra image, which is about 5 GB because the embedding model
is built in. Adra needs no internet access after that. When `docker compose ps` shows
`adra` as running, open **http://localhost:8000** to see the knowledge base.

::: tip If Adra stops right after starting
Run `docker compose logs adra`. Adra refuses to start without `LLM_API_KEY`, or when it
can't reach the storage bucket, and the log says which.
:::

## 3. Add an ADR

In the knowledge base, choose **Create ADR**, then **Create with Template** to write one,
or **Upload Document** to add an ADR you already have as a markdown file.

Agents follow ADRs closely, so write rules precisely. Say what to do, and include a
correct and an incorrect example. A rule that differs from your existing code works, as
long as the ADR says so explicitly.

## 4. Connect Claude Code

```bash
claude mcp add --scope user --transport http adra http://localhost:8000/mcp
```

Then start a **new** Claude Code session. Servers added during a session aren't loaded
until the next one.

## 5. Check that it works

1. In Claude Code, run `/mcp`. `adra` should be listed as connected, with two tools.
2. Ask for code that one of your ADRs covers. You don't need to mention Adra or ADRs.
   Claude Code calls `search_adrs` before writing, follows the ADR, and says which one it
   used.
3. Watch the agent's calls arrive with `docker compose logs -f adra`:

   ```
   INFO:     adra.mcp - search_adrs called
   INFO:     adra.retrieval - kept=[api-error-handling 0.71] dropped=[] threshold=0.58
   ```

Ask for something no ADR covers, such as a function that reverses a string, and Adra
answers that no ADR applies. The agent then writes the code following your existing
codebase.

::: info "Missing session ID" in the browser
Opening `http://localhost:8000/mcp` in a browser shows a JSON error like
`Missing session ID`. That's expected: the endpoint is for MCP clients, which open a
session first.
:::

## Next steps

- [Connect your agent](./connect-your-agent): set up Cursor or VS Code, and add one line
  to your project's instructions file so every teammate's agent checks the ADRs.
- On the **Search Tuning** page, test which ADRs a task would find, and why one wasn't
  found.
- [Run from source](./run-from-source) if you want to change Adra itself.

::: warning Before sharing with your team
Adra has no authentication, and its MCP endpoint only accepts requests addressed to
`localhost` or `127.0.0.1`. Run it on your own machine or a trusted network for now.
:::
