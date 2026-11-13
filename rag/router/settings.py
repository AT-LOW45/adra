from fastapi import APIRouter
from fastapi.responses import JSONResponse
from schema.settings_schema import CalibrateRequest, UpdateSettingsRequest
from service.settings_service import calibrate, get_settings, save_retrieval_threshold

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
