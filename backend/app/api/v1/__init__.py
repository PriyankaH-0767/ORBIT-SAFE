"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1.candidates import router as candidates_router
from app.api.v1.events import router as events_router
from app.api.v1.exports import router as exports_router
from app.api.v1.globe import router as globe_router
from app.api.v1.health import router as health_router
from app.api.v1.heatmap import router as heatmap_router
from app.api.v1.plans import router as plans_router
from app.api.v1.runs import router as runs_router
from app.api.v1.demo import router as demo_router
from app.api.v1.validation import router as validation_router

api_router = APIRouter()

# Register Phase P1 health check
api_router.include_router(health_router, tags=["Health"])

# Register Phase P13 planning, run status, candidate results, and event endpoints
api_router.include_router(plans_router, prefix="/plans", tags=["Plans"])
api_router.include_router(runs_router, prefix="/runs", tags=["Runs"])
api_router.include_router(candidates_router, prefix="/runs", tags=["Candidates"])
api_router.include_router(events_router, prefix="/runs", tags=["Events"])

# Register Phase P14 risk heatmap endpoints
api_router.include_router(heatmap_router, prefix="/runs", tags=["Heatmap"])

# Register Phase P15 3D globe visualization endpoints
api_router.include_router(globe_router, prefix="/runs", tags=["Globe"])

# Register Phase P16 external validation endpoints
api_router.include_router(validation_router, tags=["Validation"])

# Register Phase P17 CSV and PDF export endpoints
api_router.include_router(exports_router, prefix="/runs", tags=["Exports"])

# Register Phase P28 deterministic demo endpoint
api_router.include_router(demo_router, prefix="/demo", tags=["Demo"])

