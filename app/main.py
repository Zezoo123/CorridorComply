# In app/main.py
import json
import logging
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from .core.logger import setup_logging
from .middleware.logging_middleware import log_requests_middleware

# Set up logging first
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KYC Verification API",
    description="API for KYC verification with document and selfie validation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    return await log_requests_middleware(request, call_next)

# Import and include routers
from .routes import kyc, aml, risk  # noqa: E402
app.include_router(kyc.router, prefix="/api/v1/kyc", tags=["KYC"])
app.include_router(aml.router, prefix="/api/v1/aml", tags=["AML"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["Risk"])

@app.get("/")
async def root():
    """Root endpoint that returns a welcome message"""
    logger.info("Root endpoint accessed")
    return {"message": "KYC Verification API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.debug("Health check endpoint called")
    return {"status": "healthy"}

# Log unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        extra={"path": request.url.path, "method": request.method}
    )
    return Response(
        content=json.dumps({"detail": "Internal server error"}),
        status_code=500,
        media_type="application/json"
    )

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting KYC Verification API...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None  # Use Python logging configuration
    )