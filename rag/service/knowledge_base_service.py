# service/knowledge_base_service.py
import re

from langchain_core.documents import Document
from langchain_core.indexing import IndexingResult
from db.chroma_helper import (
    add_to_index,
    list_sources,
    list_records,
    get_adr_id,
    get_chunks,
    delete_from_index,
    rank_sources,
    MAX_SOURCES,
)
from exception.source_error import DuplicateSourceError, SourceDerivationError
from storage.blob_storage import upload_to_blob, get_from_blob, delete_from_blob


def next_adr_id() -> str:
    """Next sequential ADR id (e.g. 'ADR-004'), from the adr_id recorded in metadata."""
    highest = 0
    for record in list_records():
        match = re.match(r"adr-0*(\d+)", record["adr_id"], re.IGNORECASE)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"ADR-{highest + 1:03d}"


def slugify(value: str) -> str:
    """Turn a title into a URL/key-safe slug, e.g. 'ADR-003: API Auth' -> 'adr-003-api-auth'."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def source_exist(source: str, exclude: str | None = None) -> bool:
    """
    Whether a record already uses this source key. `exclude` skips one existing source —
    used when renaming, so a record isn't reported as conflicting with itself.

    The source is the title-derived key (the ADR number lives in metadata, not the key),
    so this is a plain equality check.
    """
    return any(existing == source for existing in list_sources() if existing != exclude)


def generate_source(content: str) -> str:
    """
    Derive a stable source key from the document's H1 — the TITLE only, with any
    'ADR-NNN:' prefix stripped (the number is metadata, not part of identity). This must
    stay equal to what stamp_adr_id returns, so a key can always be rebuilt from stored
    markdown (e.g. by seed_adrs.py). Returns "" if the document has no H1.
    """
    found = _find_h1(content)
    if not found:
        return ""
    title = ADR_ID_PREFIX.sub("", found[1]).strip()
    return slugify(title)


# An 'ADR-4', 'adr_012:', 'ADR 7 — ' style id at the start of a heading or filename.
# Deliberately permissive about separators so a hand-written id still gets recognised
# instead of being kept and prefixed a second time.
ADR_ID_PREFIX = re.compile(r"^adr[-_ ]*\d+\s*[:\-–—]?\s*", re.IGNORECASE)


def title_from_filename(filename: str) -> str:
    """
    Readable title from an uploaded file's name — extension and any 'adr-<n>' prefix
    removed, separators turned into spaces. The prefix strip matters because docs/adr
    files (and downloads from the UI) are already named 'adr-001-error-handling.md';
    without it a re-upload would title as 'ADR-004: adr 001 error handling'.

    The author's capitalisation is preserved as-is rather than title-cased, which would
    mangle acronyms ('API' -> 'Api').
    """
    stem = re.sub(r"\.[^.]*$", "", filename)
    stem = ADR_ID_PREFIX.sub("", stem)
    return re.sub(r"[-_]+", " ", stem).strip()


def _find_h1(content: str) -> tuple[int, str] | None:
    """(line index, heading text) of the document's first H1, or None."""
    for index, line in enumerate(content.splitlines()):
        stripped = line.strip()
        if stripped.startswith("# "):
            return index, stripped[2:].strip()
    return None


def parse_adr_id(value: str) -> str:
    """
    The 'ADR-NNN' id at the start of a source key ('adr-004-auth') or a heading
    ('ADR-4: Auth'), normalised to three digits. "" when there is none.
    """
    match = re.match(r"adr[-_ ]*0*(\d+)", value, re.IGNORECASE)
    return f"ADR-{int(match.group(1)):03d}" if match else ""


def adr_id_from_content(content: str) -> str:
    """The ADR id carried by the document's H1, or "" if it has none."""
    found = _find_h1(content)
    return parse_adr_id(found[1]) if found else ""


def stamp_adr_id(
    content: str, adr_id: str, filename: str | None = None
) -> tuple[str, str]:
    """
    Write `adr_id` onto the document's H1, returning (content, source) with
    `generate_source(content) == source` guaranteed — so the key can always be rebuilt
    from the stored markdown, including by seed_adrs.py.

    Only the 'ADR-NNN:' prefix is written; the title text is left exactly as the author
    wrote it. Any id already in the document is replaced — the number is the server's
    bookkeeping, never the client's to set.

    A document with no H1 gets one synthesised from the filename. Returns ("", "") when
    neither the heading nor the filename yields a title.
    """
    lines = content.splitlines()
    found = _find_h1(content)

    if found:
        index, heading = found
        title = ADR_ID_PREFIX.sub("", heading).strip()
        if not title:
            return "", ""
        lines[index] = f"# {adr_id}: {title}"
    else:
        title = title_from_filename(filename or "")
        if not title:
            return "", ""
        lines = [f"# {adr_id}: {title}", "", *lines]

    # The number stays in the H1 for display, but NOT in the source key — identity is
    # the title alone (generate_source strips the same 'ADR-NNN:' prefix).
    return "\n".join(lines), slugify(title)


async def create_document(
    content: str, filename: str | None = None
) -> tuple[str, IndexingResult]:
    """
    The one create path: derive identity, refuse to clobber an existing record, index.

    Serves both template-authored content (no filename) and uploaded files. Raises
    SourceDerivationError / DuplicateSourceError for the router to map to status codes —
    re-indexing a record whose source is already known goes through index_document
    directly, since overwriting is the intent there.

    The stamped content is what gets stored, so the record's H1 and its key always agree.
    """
    stamped, source = stamp_adr_id(content, next_adr_id(), filename)
    if not source:
        raise SourceDerivationError()

    # Compares title slugs with the id stripped, so the fresh number doesn't hide a
    # record that already covers this title.
    if source_exist(source):
        raise DuplicateSourceError(source)

    return source, await index_document(stamped, source)


async def update_document(source: str, content: str) -> tuple[str, IndexingResult]:
    """
    Save an edit to an existing record, returning (source, result).

    The record keeps its own number: the id is restamped from `source`, so editing the
    'ADR-NNN:' part of the heading has no effect. The *title* is the author's, and
    changing it renames the record — indexed under the new key, then removed from the old
    one — which keeps `generate_source(content) == source` true for edits as well as
    creates. A record that somehow has no number picks one up here.

    Indexes before deleting, so a failure midway leaves a duplicate (recoverable) rather
    than losing the record.
    """
    adr_id = get_adr_id(source) or next_adr_id()

    stamped, new_source = stamp_adr_id(content, adr_id)
    if not new_source:
        raise SourceDerivationError()

    # Always store `stamped`, not `content` — an id the user typed over has been reverted.
    if new_source == source:
        return source, await index_document(stamped, source)

    # Renaming onto a title another record already covers would clobber it.
    if source_exist(new_source, exclude=source):
        raise DuplicateSourceError(new_source)

    result = await index_document(stamped, new_source)
    delete_document(source)

    return new_source, result


async def index_document(content: str, source: str) -> IndexingResult:
    # store original in blob storage
    upload_to_blob(content, source)

    # index chunks in vector store. The ADR number is read back off the H1 rather than
    # passed in, so the metadata can never disagree with the stored document.
    document = Document(page_content=content, metadata={"source": source})
    result = add_to_index([document], source, adr_id_from_content(content))

    return result


def list_documents() -> list[dict]:
    """All records as {source, adr_id, title}, ordered by ADR id."""
    return list_records()


def get_document_raw(source: str) -> str:
    """The canonical markdown for a source (raises DocumentNotFoundError if missing)."""
    return get_from_blob(source)


def get_document_chunks(source: str) -> list[str]:
    """The indexed chunk texts for a source."""
    return get_chunks(source)


def delete_document(source: str) -> None:
    """Remove a document from both the vector store and blob storage."""
    delete_from_index(source, clear_key=True)
    delete_from_blob(source)


def clear_documents() -> list[str]:
    """Delete every document from both stores; returns the sources removed."""
    sources = list_sources()
    for source in sources:
        delete_document(source)
    return sources


async def search_preview(query: str, score_threshold: float) -> dict:
    """What search_adrs would return for a task, with every candidate's score.

    Goes through the same rank_sources call the agent's search does, so the page
    cannot show one outcome while agents get another. Returns the threshold it was
    evaluated at, since that is what the scores have to be read against, and the cap,
    so a caller re-deciding outcomes locally doesn't have to hardcode its own copy.
    """
    candidates = await rank_sources(query, score_threshold=score_threshold)
    return {
        "query": query,
        "retrieval_threshold": score_threshold,
        "max_sources": MAX_SOURCES,
        "candidates": candidates,
    }
