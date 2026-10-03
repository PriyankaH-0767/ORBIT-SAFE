"""Demo endpoint — GET /api/v1/demo/run (Phase P28).

Returns the canonical deterministic demo run ID. The frontend can then consume the
existing standard run/results APIs (/runs/{run_id}, /runs/{run_id}/candidates, etc.)
without any new result schema.

No existing API is changed.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.demo_service import get_or_create_demo_run
from app.services.run_service import RunService, get_run_service

logger = logging.getLogger(__name__)

router = APIRouter()


class DemoRunResponse(BaseModel):
    """Response schema for the canonical demo run endpoint."""

    run_id: str = Field(..., description="Canonical deterministic demo run identifier.")
    status: str = Field(
        default="completed",
        description="Lifecycle state of the canonical demo run (always 'completed').",
    )
    demo: bool = Field(
        default=True,
        description="Flag confirming this run is the deterministic offline demo.",
    )
    message: str = Field(
        default=(
            "Canonical deterministic demo run. "
            "Use /api/v1/runs/{run_id} and sub-resources for full results."
        ),
        description="Human-readable description of the demo run.",
    )
    data_source: str = Field(
        default="demo",
        description="Data source identifier — bundled offline demo catalog.",
    )
    reference_frame: str = Field(
        default="TEME",
        description="Coordinate reference frame used by the propagator (True Equator, Mean Equinox).",
    )
    time_scale: str = Field(
        default="UTC",
        description="Time scale used throughout (Coordinated Universal Time, ISO 8601).",
    )


@router.get(
    "/run",
    response_model=DemoRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Get canonical demo run",
    description=(
        "Returns (or lazily creates) the canonical deterministic demo run. "
        "The run is produced by executing the full D-DATO screening pipeline against the "
        "bundled offline demo TLE catalog. "
        "Subsequent calls return instantly from cache. "
        "The frontend should navigate to /results/{run_id} and use the existing "
        "/api/v1/runs/* endpoints for full result data."
    ),
    responses={
        200: {
            "description": "Canonical demo run metadata and run_id.",
            "model": DemoRunResponse,
        },
        503: {
            "description": "Demo run could not be created (e.g. demo catalog missing).",
        },
    },
)
def get_demo_run(
    db: Session = Depends(get_db),
    run_service: RunService = Depends(get_run_service),
) -> DemoRunResponse:
    """Return the canonical deterministic demo run.

    On first call this creates and executes the full screening pipeline (~90 s).
    On subsequent calls the cached run_id is returned in <1 ms.
    """
    try:
        run_id = get_or_create_demo_run(db=db, run_service=run_service)
        return DemoRunResponse(run_id=run_id)
    except FileNotFoundError as fnf:
        logger.error("Demo catalog fixture missing: %s", fnf)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DEMO_CATALOG_MISSING",
                "message": (
                    "The bundled demo catalog fixture is missing. "
                    "Ensure demo_data/tle/demo_catalog.tle or demo_data/demo_catalog.json exists."
                ),
            },
        )
    except Exception as exc:
        logger.error("Failed to get or create demo run: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DEMO_RUN_CREATION_FAILED",
                "message": str(exc),
            },
        )
