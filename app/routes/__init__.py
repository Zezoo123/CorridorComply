from . import health, kyc, aml, risk  # noqa: F401
from fastapi import APIRouter

router = APIRouter()

# Include all route modules
router.include_router(health.router, tags=["Health"])
router.include_router(kyc.router, prefix="/kyc", tags=["KYC"])
router.include_router(aml.router, prefix="/aml", tags=["AML"])
router.include_router(risk.router, prefix="/risk", tags=["Risk"])

__all__ = ["router"]