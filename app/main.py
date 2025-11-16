from fastapi import FastAPI
from .routes import health, kyc, aml, risk

def create_app() -> FastAPI:
    app = FastAPI(
        title="CorridorComply",
        version="0.1.0",
        description="Corridor-focused KYC & AML API (MVP)",
    )

    # Include routers
    app.include_router(health.router, prefix="", tags=["health"])
    app.include_router(kyc.router, prefix="/kyc", tags=["kyc"])
    app.include_router(aml.router, prefix="/aml", tags=["aml"])
    app.include_router(risk.router, prefix="/risk", tags=["risk"])

    return app


app = create_app()
