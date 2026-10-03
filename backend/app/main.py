"""D-DATO FastAPI Application Entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import settings
from app.db import init_db
from app.services.demo_service import warm_demo_cache
from app.utils.logging import get_logger, setup_logging

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for application startup and shutdown lifecycle events."""
    setup_logging(settings.LOG_LEVEL)
    logger.info(
        "Starting %s v%s (environment: %s, debug: %s)",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        settings.DEBUG,
    )
    init_db()
    warm_demo_cache()  # Phase P28: pre-build canonical demo run in background thread
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


def create_application() -> FastAPI:
    """Factory function to initialize and configure the FastAPI application."""
    application = FastAPI(
        title="D-DATO API",
        description=(
            "D-DATO (Debris-Aware Orbit & Deployment-Window Planner) is an "
            "early-stage astrodynamics screening and planning tool designed to evaluate "
            "candidate satellite deployment windows and orbital insertion parameters against "
            "cataloged space debris."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS for local development and UI integration
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API v1 router
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return application


app = create_application()

# Monorepo frontend static assets detection
_FRONTEND_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "frontend" / "dist",
    Path(__file__).resolve().parents[1] / "frontend" / "dist",
    Path.cwd() / "frontend" / "dist",
    Path("/app/frontend/dist"),
]
FRONTEND_DIST_DIR = next(
    (p for p in _FRONTEND_CANDIDATES if p.exists() and (p / "index.html").exists()),
    _FRONTEND_CANDIDATES[0],
)
INDEX_HTML = FRONTEND_DIST_DIR / "index.html"

if FRONTEND_DIST_DIR.exists() and INDEX_HTML.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    cesium_dir = FRONTEND_DIST_DIR / "cesiumStatic"
    if cesium_dir.exists():
        app.mount("/cesiumStatic", StaticFiles(directory=str(cesium_dir)), name="cesiumStatic")


@app.get("/", tags=["Root"])
def root(request: Request):
    """Root endpoint providing service metadata or UI entrypoint for browser sessions."""
    accept = request.headers.get("accept", "")
    if INDEX_HTML.exists() and "application/json" not in accept:
        return FileResponse(str(INDEX_HTML))
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
        "health_url": f"{settings.API_V1_PREFIX}/health",
    }


if FRONTEND_DIST_DIR.exists() and INDEX_HTML.exists():
    @app.get("/{full_path:path}", tags=["Frontend"], include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve compiled frontend SPA routes or static files."""
        file_path = FRONTEND_DIST_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(INDEX_HTML))

