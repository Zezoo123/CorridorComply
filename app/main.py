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

# Startup event: Check and update sanctions lists if needed
@app.on_event("startup")
async def startup_sanctions_update():
    """
    Check if sanctions lists need updating on API server startup.
    Updates automatically if lists are older than configured interval.
    """
    from .config import SANCTIONS_AUTO_UPDATE_ENABLED, SANCTIONS_UPDATE_INTERVAL_DAYS
    from .services.sanctions_loader import SanctionsLoader
    import subprocess
    import sys
    from pathlib import Path
    
    if not SANCTIONS_AUTO_UPDATE_ENABLED:
        logger.info("Sanctions auto-update is disabled (set SANCTIONS_AUTO_UPDATE_ENABLED=true to enable)")
        return
    
    try:
        logger.info("Checking if sanctions lists need updating...")
        needs_update, age_days = SanctionsLoader.check_if_update_needed(
            update_interval_days=SANCTIONS_UPDATE_INTERVAL_DAYS
        )
        
        if needs_update:
            if age_days is not None:
                logger.info(f"Sanctions lists are {age_days:.1f} days old (threshold: {SANCTIONS_UPDATE_INTERVAL_DAYS} days)")
            logger.info("Starting automatic sanctions list update...")
            
            # Run the update script in background (non-blocking)
            script_path = Path(__file__).parent.parent / "scripts" / "update_sanctions.py"
            if script_path.exists():
                # Run update in background thread to not block server startup
                import asyncio
                import threading
                
                def run_update():
                    try:
                        result = subprocess.run(
                            [sys.executable, str(script_path)],
                            capture_output=True,
                            text=True,
                            timeout=1800  # 30 minute timeout
                        )
                        if result.returncode == 0:
                            logger.info("✅ Sanctions lists updated successfully")
                            # Clear cache so new data is loaded
                            SanctionsLoader.clear_cache()
                        else:
                            logger.warning(f"⚠️  Sanctions update completed with warnings (exit code: {result.returncode})")
                    except Exception as e:
                        logger.error(f"Error during sanctions update: {str(e)}")
                
                # Run in background thread
                update_thread = threading.Thread(target=run_update, daemon=True)
                update_thread.start()
                logger.info("Sanctions update running in background...")
            else:
                logger.warning(f"Update script not found: {script_path}")
        else:
            logger.info(f"Sanctions lists are up to date (age: {age_days:.1f} days)")
            
    except Exception as e:
        logger.error(f"Error checking/updating sanctions lists: {str(e)}", exc_info=True)
        # Don't fail startup if update check fails

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