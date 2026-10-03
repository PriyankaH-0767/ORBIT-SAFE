"""Risk heatmap matrix endpoints (Phase P14).

The original D-DATO specification is authoritative.
Retrieves 2D risk heatmap matrix partitioned by orbital inclination slices.
Read-only endpoint: does not restart, rescreen, rerank, or trigger workers.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.heatmap import HeatmapResponse
from app.services.heatmap_service import HeatmapService, get_heatmap_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{run_id}/heatmap",
    response_model=HeatmapResponse,
    status_code=status.HTTP_200_OK,
    summary="Get risk heatmap matrix",
    description=(
        "Retrieves a 2D risk density matrix for a screening run. "
        "The X axis represents deployment delay in minutes, the Y axis represents altitude in km, "
        "and layers are sliced by orbital inclination in degrees. Values correspond to persisted risk scores (0-100). "
        "Missing grid positions are represented as null."
    ),
    responses={
        200: {
            "description": "Risk heatmap matrix data successfully retrieved.",
            "model": HeatmapResponse,
        },
        404: {
            "description": "Run not found.",
        },
        422: {
            "description": "Malformed inclination query parameter.",
        },
        500: {
            "description": "Internal server error retrieving heatmap data.",
        },
    },
)
def get_run_heatmap(
    run_id: str,
    inclination_deg: Optional[float] = Query(
        default=None,
        description="Optional orbital inclination filter in degrees. If omitted, returns all inclination layers.",
    ),
    db: Session = Depends(get_db),
    heatmap_service: HeatmapService = Depends(get_heatmap_service),
) -> HeatmapResponse:
    """Retrieve 2D risk heatmap matrix for a screening run."""
    try:
        return heatmap_service.get_run_heatmap(
            run_id=run_id,
            inclination_deg=inclination_deg,
            db=db,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RUN_NOT_FOUND", "message": f"Run '{run_id}' was not found."},
        )
    except Exception as exc:
        logger.error("Unexpected error retrieving heatmap for run '%s': %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "HEATMAP_RETRIEVAL_ERROR", "message": str(exc)},
        )
