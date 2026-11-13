# service/settings_service.py
import json
import logging

from config.review_config import DEFAULT_SECTIONS
from db.chroma_helper import SCORE_THRESHOLD, rank_sources
from schema.knowledgebase_schema import SectionSpec
from storage.blob_storage import (
    ADR_FORMAT_KEY,
    LEGACY_SETTINGS_KEY,
    RETRIEVAL_SETTINGS_KEY,
    delete_settings_from_blob,
    get_settings_from_blob,
    save_settings_to_blob,
)

logger = logging.getLogger("adra.settings")

# Saved settings, one dict per settings file, read from the bucket once and then kept in
# memory: search_adrs runs on every agent request, and a bucket round trip per search
# would be wasted. Saving goes through _write, which refreshes this, so a change applies
# without a restart.
_cache: dict[str, dict] = {}


def _load(key: str) -> dict:
    if key not in _cache:
        raw = get_settings_from_blob(key)
        if raw is None and key == RETRIEVAL_SETTINGS_KEY:
            # Saved by v0.2.0 under the old name and not re-saved since.
            raw = get_settings_from_blob(LEGACY_SETTINGS_KEY)
        _cache[key] = json.loads(raw) if raw else {}
    return _cache[key]


def _write(key: str, settings: dict) -> None:
    """Save a settings file, refreshing the cache only once the write succeeded, so a
    failed save can't leave the server using a value that isn't in the bucket."""
    save_settings_to_blob(key, json.dumps(settings))
    _cache[key] = settings


# Retrieval: the relevance threshold search_adrs uses.


def retrieval_threshold() -> float:
    """The threshold to search with: a saved value, else RETRIEVAL_THRESHOLD, else 0.58."""
    saved = _load(RETRIEVAL_SETTINGS_KEY).get("retrieval_threshold")
    return float(saved) if saved is not None else SCORE_THRESHOLD


def get_settings() -> dict:
    """Current settings, plus whether the threshold was saved or comes from the default."""
    saved = _load(RETRIEVAL_SETTINGS_KEY).get("retrieval_threshold")
    return {
        "retrieval_threshold": retrieval_threshold(),
        "retrieval_threshold_source": "saved" if saved is not None else "default",
        "default_retrieval_threshold": SCORE_THRESHOLD,
    }


def save_retrieval_threshold(retrieval_threshold: float | None) -> dict:
    """Save the threshold, or clear it (None) to fall back to the default. Applies at once."""
    settings = dict(_load(RETRIEVAL_SETTINGS_KEY))
    if retrieval_threshold is None:
        settings.pop("retrieval_threshold", None)
    else:
        settings["retrieval_threshold"] = retrieval_threshold
    _write(RETRIEVAL_SETTINGS_KEY, settings)
    _remove_legacy_settings()
    shown = f"default ({SCORE_THRESHOLD})" if retrieval_threshold is None else retrieval_threshold
    logger.info("retrieval_threshold set to %s", shown)
    return get_settings()


def _remove_legacy_settings() -> None:
    """Delete the v0.2.0 settings file once retrieval.json holds its contents.

    Best effort: the save has already succeeded, and a leftover legacy file is harmless,
    since it's only read while retrieval.json doesn't exist.
    """
    try:
        delete_settings_from_blob(LEGACY_SETTINGS_KEY)
    except Exception as error:
        logger.warning("couldn't remove %s: %s", LEGACY_SETTINGS_KEY, error)


# The ADR format: the sections an ADR has, which the Create form renders and the quality
# review checks against. One format per instance (#2). Existing ADRs are never rewritten
# when it changes; it only affects new ADRs and reviews. Stored as {"sections": [...]};
# no file means the default.


def adr_format() -> list[SectionSpec]:
    """The ADR format in use: the saved one, else DEFAULT_SECTIONS.

    Returns copies, so a caller changing what it gets back can't change the cached format.
    """
    saved = _load(ADR_FORMAT_KEY).get("sections")
    sections = saved if saved is not None else DEFAULT_SECTIONS
    return [SectionSpec(title=s["title"], purpose=s["purpose"], required=s["required"]) for s in sections]


def adr_format_is_saved() -> bool:
    """Whether a team saved its own format, as opposed to using the default."""
    return _load(ADR_FORMAT_KEY).get("sections") is not None


def validate_adr_format(sections: list[SectionSpec]) -> list[SectionSpec]:
    """Normalize a format and reject one the review couldn't use. Raises ValueError.

    Titles are trimmed and must be non-empty and unique ignoring case, because the review
    matches `## ` headings to sections case-insensitively: two titles differing only in
    case would be one section to it. A title can't contain a line break, since it becomes
    a single heading line.
    """
    if not sections:
        raise ValueError("An ADR format needs at least one section.")

    normalized: list[SectionSpec] = []
    seen: set[str] = set()
    for section in sections:
        title = section["title"].strip()
        if not title:
            raise ValueError("Every section needs a title.")
        if "\n" in title or "\r" in title:
            raise ValueError(f"Section title {title!r} can't contain a line break.")
        if title.lower() in seen:
            raise ValueError(f"Section {title!r} appears more than once.")
        seen.add(title.lower())
        normalized.append(
            SectionSpec(title=title, purpose=section["purpose"].strip(), required=bool(section["required"]))
        )
    return normalized


def save_adr_format(sections: list[SectionSpec] | None) -> list[SectionSpec]:
    """Save the ADR format, or clear it (None) to go back to DEFAULT_SECTIONS. Applies at once.

    Returns the format now in use.
    """
    if sections is None:
        delete_settings_from_blob(ADR_FORMAT_KEY)
        _cache[ADR_FORMAT_KEY] = {}
        logger.info("adr_format reset to the default")
    else:
        normalized = validate_adr_format(sections)
        _write(ADR_FORMAT_KEY, {"sections": normalized})
        logger.info("adr_format saved with %d sections", len(normalized))
    return adr_format()


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
