from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from schema.knowledgebase_schema import SectionSpec
from schema.settings_schema import CalibrateRequest, UpdateAdrFormatRequest, UpdateSettingsRequest
from service.settings_service import (
    calibrate,
    get_adr_format_settings,
    get_settings,
    save_adr_format,
    save_retrieval_threshold,
)

# Team-level settings, stored in the blob bucket so they are backed up with the ADRs.
router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
async def get_settings_endpoint():
    """Current settings, and whether the threshold was saved or is the default."""
    return JSONResponse(content=get_settings())


@router.put("")
async def update_settings_endpoint(request: UpdateSettingsRequest):
    """Save settings. They apply immediately, with no restart."""
    return JSONResponse(content=save_retrieval_threshold(request.retrieval_threshold))


@router.post("/calibrate")
async def calibrate_endpoint(request: CalibrateRequest):
    """Suggest a threshold from tasks the ADRs cover and tasks they deliberately don't.

    Suggests only; saving stays an explicit PUT, so a suggestion can be inspected and
    rejected rather than applied the moment it is calculated.
    """
    return JSONResponse(content=await calibrate(request.genuine, request.unrelated))


@router.get("/adr-format")
async def get_adr_format_endpoint():
    """The ADR format in use, whether it was saved or is the default, and the default."""
    return JSONResponse(content=get_adr_format_settings())


@router.put("/adr-format")
async def update_adr_format_endpoint(request: UpdateAdrFormatRequest):
    """Save the ADR format, or reset it with `sections: null`. Applies immediately.

    Existing ADRs aren't changed; the format affects the Create form and the quality review.
    """
    sections = (
        None
        if request.sections is None
        else [SectionSpec(title=s.title, purpose=s.purpose, required=s.required) for s in request.sections]
    )
    try:
        return JSONResponse(content=save_adr_format(sections))
    except ValueError as error:
        # Checks that span sections (duplicate titles, an empty list), which the request
        # schema can't express per field.
        raise HTTPException(status_code=422, detail=str(error))
