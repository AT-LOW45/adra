# main.py
import os

import uvicorn
from dotenv import load_dotenv

# Also called in config/llm_config.py, but that module is not imported until uvicorn
# loads "server:app" — i.e. after the call below. Without this, HOST/PORT/RELOAD would
# see real environment variables but silently ignore anything set in .env.
load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        # Defaults match how this has always run locally. A container must set
        # HOST=0.0.0.0, or 127.0.0.1 binds inside the container only and the published
        # port refuses connections from the host.
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        # Reload watches the filesystem — a development convenience, off in a container.
        reload=os.getenv("RELOAD", "true").lower() == "true",
    )
