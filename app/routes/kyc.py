from fastapi import APIRouter
from ..models.kyc import KYCRequest, KYCResponse

router = APIRouter()

@router.post("/verify", response_model=KYCResponse)
async def verify_kyc(payload: KYCRequest):
    """
    Simple KYC stub endpoint.
    Later: call OCR, face match, risk engine, etc.
    """
    # For now, just echo back some dummy result
    return KYCResponse(
        status="pass",
        risk_score=10,
        details=["KYC endpoint stub – logic to be implemented"],
    )
