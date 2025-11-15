from fastapi import APIRouter
from ..models.aml import AMLScreenRequest, AMLScreenResponse

router = APIRouter()

@router.post("/screen", response_model=AMLScreenResponse)
async def screen_aml(payload: AMLScreenRequest):
    """
    Simple AML stub endpoint.
    Later: sanctions screening, PEP, fuzzy matching, etc.
    """
    return AMLScreenResponse(
        sanctions_match=False,
        pep_match=False,
        risk_score=5,
        details=["AML endpoint stub – logic to be implemented"],
    )
