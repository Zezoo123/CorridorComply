from fastapi import APIRouter
from ..models.aml import AMLScreenRequest, AMLScreenResponse
from ..services.aml_service import AMLService

router = APIRouter()

@router.post("/screen", response_model=AMLScreenResponse)
async def screen_aml(payload: AMLScreenRequest):
    result = AMLService.screen(
        full_name=payload.full_name,
        dob=payload.dob,
        nationality=payload.nationality,
    )

    return AMLScreenResponse(**result)