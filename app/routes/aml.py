from fastapi import APIRouter
from ..models.aml import AMLScreenRequest, AMLScreenResponse
from ..services.aml_service import AMLService
from ..core.utils import generate_request_id

router = APIRouter()

@router.post("/screen", response_model=AMLScreenResponse)
async def screen_aml(payload: AMLScreenRequest):
    request_id = generate_request_id()
    
    result = AMLService.screen(
        request_id=request_id,
        full_name=payload.full_name,
        dob=payload.dob,
        nationality=payload.nationality,
    )

    return AMLScreenResponse(**result)