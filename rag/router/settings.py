from fastapi import APIRouter
from fastapi.responses import JSONResponse
from schema.settings_schema import UpdateSettingsRequest
from service.settings_service import get_settings, update_settings

# Team-level settings, stored in the blob bucket so they are backed up with the ADRs.
router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
async def get_settings_endpoint():
    """Current settings, and whether the threshold was saved or is the default."""
    return JSONResponse(content=get_settings())


@router.put("")
async def update_settings_endpoint(request: UpdateSettingsRequest):
    """Save settings. They apply immediately, with no restart."""
    return JSONResponse(content=update_settings(request.retrieval_threshold))
