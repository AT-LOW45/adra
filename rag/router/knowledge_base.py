
from exception.document_not_found_error import DocumentNotFoundError
from exception.source_error import DuplicateSourceError, SourceDerivationError
from fastapi.responses import JSONResponse
from fastapi import HTTPException, UploadFile, File, APIRouter
from schema.boilerplate_schema import CreateDocumentRequest
from schema.knowledgebase_schema import SearchPreviewRequest
from service.knowledge_base_service import (
    create_document as kb_create_document,
    update_document as kb_update_document,
    next_adr_id,
    list_documents,
    get_document_raw,
    get_document_chunks,
    delete_document,
    clear_documents,
    search_preview,
)
from service.review_service import review_adr
from service.settings_service import retrieval_threshold

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])


@router.post("")
async def create_document_endpoint(request: CreateDocumentRequest):
    """Create a new record through UI template. The source key is derived server-side from the
    document's H1 title — callers do not supply it."""
    try:
        source, result = await kb_create_document(request.content)
    except SourceDerivationError:
        raise HTTPException(
            status_code=400,
            detail="Could not derive a source: the document needs a top-level '# ' title.",
        )
    except DuplicateSourceError:
        raise HTTPException(
            status_code=409,
            detail="ADR with this title already exists, try using another one",
        )

    return JSONResponse(content={"source": source, "result": result})


@router.post("/index-document")
async def index_document_endpoint(file: UploadFile = File(...), source: str = ""):
    """Two intents behind one endpoint, told apart by whether `source` is supplied.

    With a source: save an edit to that record. The edited H1 stays authoritative, so a
    changed title renames the record rather than leaving its key stale.

    Without one: create from an uploaded file, same rule as the template path."""
    content = await file.read()
    text = content.decode("utf-8")

    if source:
        try:
            renamed, result = await kb_update_document(source, text)
        except SourceDerivationError:
            raise HTTPException(
                status_code=400,
                detail="Could not derive a source: the document needs a top-level '# ' title.",
            )
        except DuplicateSourceError as conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Another ADR already covers '{conflict.source}' — pick a different title.",
            )

        return JSONResponse(content={"source": renamed, "result": result})

    try:
        source_name, result = await kb_create_document(text, file.filename)
    except SourceDerivationError:
        raise HTTPException(
            status_code=400,
            detail="Could not derive a source: the file needs a top-level '# ' title or a usable filename.",
        )
    except DuplicateSourceError as conflict:
        raise HTTPException(
            status_code=409,
            detail=f"An ADR matching '{conflict.source}' already exists — rename the file, or edit the existing record instead.",
        )

    return JSONResponse(content={"source": source_name, "result": result})


@router.get("/next-id")
async def next_id_endpoint():
    """The next sequential ADR id to pre-fill the create form. Best-effort — not a
    reservation, so concurrent creates could collide (see overwrite handling)."""
    return JSONResponse(content={"id": next_adr_id()})


@router.get("/{source}/raw")
async def get_document_raw_endpoint(source: str):
    try:
        content = get_document_raw(source)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document '{source}' not found")
    return JSONResponse(content={"source": source, "content": content})


@router.get("")
async def list_documents_endpoint():
    return JSONResponse(content={"records": list_documents()})


@router.get("/{source}")
async def get_document_content_endpoint(source: str):
    chunks = get_document_chunks(source)
    return JSONResponse(
        content={"source": source, "chunks": chunks, "chunk_count": len(chunks)}
    )


@router.delete("/{source}")
async def delete_document_endpoint(source: str):
    delete_document(source)
    return JSONResponse(content={"deleted": source})


@router.delete("")
async def clear_knowledge_base_endpoint():
    return JSONResponse(content={"deleted": clear_documents()})


@router.post("/adr-review")
async def review_adr_endpoint(content: CreateDocumentRequest):
    return await review_adr(content.content)


@router.post("/search-preview")
async def search_preview_endpoint(request: SearchPreviewRequest):
    """Run a coding task through retrieval and report every candidate ADR's score.

    Answers "why did this task retrieve that ADR, or nothing at all" without reading
    server logs. Threshold defaults to the one agents are served; passing one tries a
    value before committing it through PUT /settings.
    """
    threshold = (
        request.retrieval_threshold
        if request.retrieval_threshold is not None
        else retrieval_threshold()
    )
    return JSONResponse(content=await search_preview(request.query, threshold))
