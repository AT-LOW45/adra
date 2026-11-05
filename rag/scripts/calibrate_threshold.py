"""
Calibrate the retrieval score_threshold used in db/chroma_helper.search_index.

Run it whenever you change the embedding model or add a batch of ADRs, because the
"right" threshold depends on how the current model scores your current content.

How it works: it scores a set of GENUINE queries (coding tasks an ADR covers) and a set
of JUNK queries (coding tasks no ADR covers). The threshold should sit in the gap between
the lowest genuine score and the highest junk score. A wide gap = robust; no gap = the
model can't tell relevant from irrelevant and no threshold will fix it.

JUNK must be realistic coding tasks, not off-topic text: an agent never asks about
cookie recipes, but it does ask for a CSV parser. Off-topic junk scores far lower, so
calibrating against it suggests a threshold that lets unrelated coding tasks through.

Usage (must run from the rag/ directory so imports resolve):
    cd rag
    uv run python scripts/calibrate_threshold.py

Edit the GENUINE and JUNK lists below to match your own knowledge base, then set the
suggested value as RETRIEVAL_THRESHOLD in .env.
"""

import asyncio
import sys
from pathlib import Path

# allow running as `python scripts/calibrate_threshold.py` from the rag/ dir
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.chroma_helper import vector_store, search_index  # noqa: E402

# --- edit these to reflect your own ADRs ------------------------------------
# Coding tasks that an ADR in the knowledge base covers (these match docs/adr samples).
GENUINE = [
    "create a hook to fetch a list of products for a customer",
    "async function to fetch orders by customer with error handling",
    "protect an API route so only authenticated users can call it",
    "verify the JWT bearer token on incoming requests",
    "react hook to fetch a list of products",
]

# Coding tasks that no ADR covers: the agent should get nothing back for these.
JUNK = [
    "Python helper function to parse a CSV line",
    "write a function to reverse a string",
    "convert a datetime to ISO 8601 in UTC",
    "rename a variable across the module",
    "write a regex that validates an email address",
    "sort a list of dicts by a key",
]
# ----------------------------------------------------------------------------


async def top_score(query: str) -> float:
    """Best relevance score across all chunks for a query (the deciding score)."""
    results = await vector_store.asimilarity_search_with_relevance_scores(query, k=50)
    return max((score for _, score in results), default=float("-inf"))


async def main() -> None:
    genuine_scores = [(q, await top_score(q)) for q in GENUINE]
    junk_scores = [(q, await top_score(q)) for q in JUNK]

    print("\nGENUINE queries (should be retrieved):")
    for q, s in genuine_scores:
        print(f"  {s:6.3f}  {q}")
    print("\nJUNK queries (should return nothing):")
    for q, s in junk_scores:
        print(f"  {s:6.3f}  {q}")

    floor = min(s for _, s in genuine_scores)   # lowest genuine
    ceiling = max(s for _, s in junk_scores)     # highest junk
    gap = floor - ceiling

    print("\n" + "-" * 50)
    print(f"genuine floor : {floor:.3f}")
    print(f"junk ceiling  : {ceiling:.3f}")
    print(f"gap           : {gap:.3f}")
    if gap > 0:
        suggested = round((floor + ceiling) / 2, 3)
        print(f"\n==> suggested RETRIEVAL_THRESHOLD: {suggested}")
        print("    (midpoint of the gap; wider gap = more robust)")
    else:
        print("\n==> NO GAP: genuine and junk overlap. No single threshold separates")
        print("    them — the embedding model can't discriminate these queries.")


if __name__ == "__main__":
    asyncio.run(main())
