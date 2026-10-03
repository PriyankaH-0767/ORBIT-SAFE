"""Screening run lifecycle status and execution polling endpoints (Phase P13).

The original D-DATO specification is authoritative.
GET /runs/{run_id} is strictly read-only and reflects persisted execution state.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.run import RunStatusResponse
from app.services.run_service import RunService, get_run_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{run_id}",
    response_model=RunStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get run status",
    description="Retrieves current execution lifecycle status, progress percent, stage, and entity counts for a screening run.",
    responses={
        200: {"description": "Current screening run execution state.", "model": RunStatusResponse},
        404: {"description": "Run not found."},
    },
)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    run_service: RunService = Depends(get_run_service),
) -> RunStatusResponse:
    """Retrieve execution progress and status metadata for a specific screening run."""
    try:
        summary = run_service.get_run_status(run_id, db=db)
        return summary.to_response()
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RUN_NOT_FOUND", "message": f"Run '{run_id}' was not found."},
        )
    except Exception as exc:
        logger.error("Unexpected error retrieving run '%s': %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "RUN_STATUS_ERROR", "message": str(exc)},
        )
