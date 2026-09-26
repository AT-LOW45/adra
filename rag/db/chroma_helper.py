from pathlib import Path

from langchain_chroma.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_core.documents import Document
from langchain_core.indexing import IndexingResult, index
from langchain_classic.indexes import SQLRecordManager

# Anchored to this file's location rather than a bare "./chroma_db" — a relative path
# resolves against the process's cwd, so running a script from rag/scripts instead of
# rag/ would silently open (or create) a second, empty store. See rekey_sources.py.
_RAG_DIR = Path(__file__).resolve().parent.parent
CHROMA_DB_PATH = str(_RAG_DIR / "chroma_db")
# .as_posix() (forward slashes) rather than str() — SQLAlchemy's sqlite URL scheme
# breaks on Windows-style backslashes in the path.
RECORD_MANAGER_DB = f"sqlite:///{(_RAG_DIR / 'record_manager.db').as_posix()}"
# Kept as "patterngen" through the rename to Adra: this is the record-manager key for
# incremental indexing. Changing it orphans every already-indexed document, so a
# re-upload would duplicate chunks instead of replacing them.
NAMESPACE = "chroma/patterngen"

# bge-base-en-v1.5 is a stronger, code/architecture-aware retrieval model than
# all-MiniLM-L6-v2. It wants normalized embeddings + cosine distance, and a query
# instruction prefix for asymmetric (short query -> long passage) retrieval.
# Note: 768-dim — changing this model requires rebuilding the Chroma collection.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-base-en-v1.5",
    encode_kwargs={"normalize_embeddings": True},
    query_encode_kwargs={
        "normalize_embeddings": True,
        "prompt": BGE_QUERY_INSTRUCTION,
    },
)

vector_store = Chroma(
    persist_directory=CHROMA_DB_PATH,
    embedding_function=embeddings,
    collection_metadata={"hnsw:space": "cosine"},
)

record_manager = SQLRecordManager(namespace=NAMESPACE, db_url=RECORD_MANAGER_DB)
record_manager.create_schema()

header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "title"),
        ("##", "section"),
        ("###", "subsection"),
    ],
    strip_headers=False,
)


def split_documents(documents: list[Document]) -> list[Document]:
    chunks = []
    for doc in documents:
        header_chunks = header_splitter.split_text(doc.page_content)
        for order, chunk in enumerate(header_chunks):
            chunk.metadata.update(doc.metadata)
            # preserve original document order so an ADR can be reassembled
            chunk.metadata["chunk_index"] = order
        chunks.extend(header_chunks)
    return chunks


def add_to_index(
    documents: list[Document], source: str, adr_id: str = ""
) -> IndexingResult:
    """Index a document's chunks under `source`.

    `adr_id` ('ADR-004') is recorded alongside so the number can be read without parsing
    the markdown — it stays out of `source` itself only once the key is decoupled (see
    issue #3); for now it is duplicated information kept in sync by the caller.
    """
    for doc in documents:
        doc.metadata["source"] = source
        if adr_id:
            doc.metadata["adr_id"] = adr_id

    # split_documents copies doc.metadata onto every chunk, so setting it here is enough.
    chunks = split_documents(documents)

    result = index(
        chunks,
        record_manager,
        vector_store,
        cleanup="incremental",
        source_id_key="source",
    )
    return result


def _assemble_source(source: str) -> str:
    """Fetch every chunk of one ADR and reassemble it in document order."""
    stored = vector_store.get(where={"source": source})
    pairs = list(zip(stored["metadatas"], stored["documents"]))
    pairs.sort(key=lambda p: p[0].get("chunk_index", 0))
    return "\n\n".join(doc for _, doc in pairs)


async def search_index(
    query: str,
    candidate_k: int = 36,
    score_threshold: float = 0.5,
    max_sources: int = 3,
) -> str:
    """
    Find which ADRs are relevant to the query, then return each relevant ADR in
    full (not just the matched chunks) so code examples are never dropped.

    - candidate_k: how many chunks to inspect when deciding which ADRs are relevant
    - score_threshold: an ADR's best-matching chunk must clear this to be included
    - max_sources: cap on how many ADRs to return, so a vague query can't pull in everything
    """
    scored = await vector_store.asimilarity_search_with_relevance_scores(
        query, k=candidate_k
    )

    # keep each source's best chunk score
    best_score: dict[str, float] = {}
    for doc, score in scored:
        source = doc.metadata.get("source")
        if source is None:
            continue
        if score > best_score.get(source, float("-inf")):
            best_score[source] = score

    # keep relevant sources, strongest first, capped
    relevant = sorted(
        (s for s, score in best_score.items() if score >= score_threshold),
        key=lambda s: best_score[s],
        reverse=True,
    )[:max_sources]

    if not relevant:
        return ""

    return "\n\n---\n\n".join(_assemble_source(source) for source in relevant)


def list_sources() -> list[str]:
    """All unique source keys currently in the vector store."""
    results = vector_store.get()
    return sorted({m.get("source", "") for m in results["metadatas"] if m.get("source")})


def list_records() -> list[dict]:
    """One entry per source — {source, adr_id, title} — ordered by adr_id.

    The ADR number lives in metadata (not the source key), so ordering and display
    read it from here rather than parsing the key.
    """
    records: dict[str, dict] = {}
    for metadata in vector_store.get()["metadatas"]:
        source = metadata.get("source")
        if not source or source in records:
            continue
        records[source] = {
            "source": source,
            "adr_id": metadata.get("adr_id", ""),
            "title": metadata.get("title", source),
        }
    return sorted(records.values(), key=lambda r: r["adr_id"])


def get_adr_id(source: str) -> str:
    """The ADR id recorded for a source, or "" if it has none."""
    for metadata in vector_store.get(where={"source": source})["metadatas"]:
        if metadata.get("adr_id"):
            return metadata["adr_id"]
    return ""


def get_chunks(source: str) -> list[str]:
    """All stored chunk texts for one source."""
    results = vector_store.get(where={"source": source})
    return results["documents"]


def delete_from_index(source: str, clear_key: bool = False) -> None:
    """
    clears document from vector store while persisting the record. If clear_key is True, clears the record entirely
    """
    # delete from vector store
    vector_store.delete(where={"source": source})

    # # delete from record manager
    if clear_key:
        keys = record_manager.list_keys(group_ids=[source])
        if keys:
            record_manager.delete_keys(keys)
