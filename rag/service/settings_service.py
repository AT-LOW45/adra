# service/settings_service.py
import json
import logging

from db.chroma_helper import SCORE_THRESHOLD, rank_sources
from storage.blob_storage import get_settings_from_blob, save_settings_to_blob

logger = logging.getLogger("adra.settings")

# Saved settings, read from the bucket once and then kept in memory: search_adrs runs on
# every agent request, and a bucket round trip per search would be wasted. Saving goes
# through update_settings, which refreshes this, so a change applies without a restart.
_saved: dict | None = None


def _load() -> dict:
    global _saved
    if _saved is None:
        raw = get_settings_from_blob()
        _saved = json.loads(raw) if raw else {}
    return _saved or {}


def retrieval_threshold() -> float:
    """The threshold to search with: a saved value, else RETRIEVAL_THRESHOLD, else 0.58."""
    saved = _load().get("retrieval_threshold")
    return float(saved) if saved is not None else SCORE_THRESHOLD


def get_settings() -> dict:
    """Current settings, plus whether the threshold was saved or comes from the default."""
    saved = _load().get("retrieval_threshold")
    return {
        "retrieval_threshold": retrieval_threshold(),
        "retrieval_threshold_source": "saved" if saved is not None else "default",
        "default_retrieval_threshold": SCORE_THRESHOLD,
    }


def update_settings(retrieval_threshold: float | None) -> dict:
    """Save the threshold, or clear it (None) to fall back to the default. Applies at once."""
    global _saved
    settings = dict(_load())
    if retrieval_threshold is None:
        settings.pop("retrieval_threshold", None)
    else:
        settings["retrieval_threshold"] = retrieval_threshold
    save_settings_to_blob(json.dumps(settings))
    _saved = settings
    shown = f"default ({SCORE_THRESHOLD})" if retrieval_threshold is None else retrieval_threshold
    logger.info("retrieval_threshold set to %s", shown)
    return get_settings()


async def _top_score(query: str) -> float | None:
    """The score that decides whether a query retrieves anything at all.

    Scored through rank_sources, the same path agents go through, so a suggestion
    cannot be derived from numbers that differ from the ones in use. None when the
    knowledge base is empty and there is nothing to score against.
    """
    candidates = await rank_sources(query, score_threshold=0.0)
    return candidates[0]["score"] if candidates else None


async def calibrate(genuine: list[str], unrelated: list[str]) -> dict:
    """Suggest a threshold from tasks the ADRs cover and tasks they don't.

    The threshold belongs in the gap between the lowest genuine score and the highest
    unrelated one: above every task that should match, below every task that should
    not. The midpoint is the most forgiving choice, leaving equal room either side as
    the knowledge base changes.

    A gap of zero or less means the two overlap, and no single threshold separates
    them. That is not a calibration failure to work around -- it says retrieval cannot
    tell these queries apart, and the fix is clearer ADRs or a different embedding
    model. suggested_threshold is None in that case rather than a number that would
    quietly have to sacrifice one side.

    Mirrors scripts/calibrate_threshold.py, which does the same for anyone with a clone.
    """
    genuine_scores = [{"query": q, "score": await _top_score(q)} for q in genuine]
    unrelated_scores = [{"query": q, "score": await _top_score(q)} for q in unrelated]

    scored_genuine = [r["score"] for r in genuine_scores if r["score"] is not None]
    scored_unrelated = [r["score"] for r in unrelated_scores if r["score"] is not None]

    if not scored_genuine or not scored_unrelated:
        return {
            "genuine": genuine_scores,
            "unrelated": unrelated_scores,
            "floor": None,
            "ceiling": None,
            "gap": None,
            "suggested_threshold": None,
        }

    floor = min(scored_genuine)
    ceiling = max(scored_unrelated)
    gap = floor - ceiling
    return {
        "genuine": genuine_scores,
        "unrelated": unrelated_scores,
        "floor": floor,
        "ceiling": ceiling,
        "gap": gap,
        "suggested_threshold": round((floor + ceiling) / 2, 3) if gap > 0 else None,
    }
