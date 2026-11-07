# service/settings_service.py
import json
import logging

from db.chroma_helper import SCORE_THRESHOLD
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
