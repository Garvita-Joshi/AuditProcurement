# this file creates API application and is used as entry points for the APIs

# main.py creates the FastAPI app, allows the React frontend to call it
# connects all API route files, provides a basic health check
# and starts the server locally on port 8000

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.claims import router as claims_router
from backend.app.api.receipts import router as receipts_router
from backend.app.api.fraud import router as fraud_router
from backend.app.api.reports import router as reports_router
from backend.app.api.cases import router as cases_router
from backend.app.api.analytics import router as analytics_router
from backend.app.api.auth import router as auth_router
from backend.app.api.control_points import router as control_points_router
from backend.app.api.ingestion import router as ingestion_router
from backend.app.api.procurement import router as procurement_router
from backend.app.api.procurement_payments import router as procurement_payments_router
from backend.app.api.procurement_extraction import router as procurement_extraction_router
from backend.app.api.sourcing import router as sourcing_router
from backend.app.config import CORS_ORIGINS
from backend.app.core.security import require_authenticated_user

app = FastAPI(
    title="AuditAI API",
    description="Automated financial anomaly detection and ingestion pipeline.",
    version="1.0.0"
)

# Enable CORS for frontend integration
# later in here we can also integrate this with JWT for secuirty and authentication
# Adjust for production when u expand
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register endpoints
app.include_router(auth_router)
app.include_router(sourcing_router)
auth_required = [Depends(require_authenticated_user)]
app.include_router(claims_router, dependencies=auth_required)
app.include_router(receipts_router, dependencies=auth_required)
app.include_router(fraud_router, dependencies=auth_required)
app.include_router(reports_router, dependencies=auth_required)
app.include_router(cases_router, dependencies=auth_required)
app.include_router(analytics_router, dependencies=auth_required)
app.include_router(ingestion_router, dependencies=auth_required)
app.include_router(control_points_router, dependencies=auth_required)
app.include_router(procurement_router, dependencies=auth_required)
app.include_router(procurement_payments_router, dependencies=auth_required)
app.include_router(procurement_extraction_router, dependencies=auth_required)

@app.get("/")
def read_root():
# It confirms that the backend server is running so it is basically a small checkpoint
    return {
        "app": "AuditAI",
        "description": "Financial Transaction Anomaly Detection & Ingestion Engine",
        "version": "1.0.0",
        "status": "healthy"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
