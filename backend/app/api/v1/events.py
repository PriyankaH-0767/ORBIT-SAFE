"""Conjunction events and close-approach encounters API endpoints (Phase P13).

The original D-DATO specification is authoritative.
Retrieves close-approach conjunction events detected during a screening run with database-level pagination.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.event import EventResultsResponse
from app.services.run_service import RunService, get_run_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{run_id}/events",
    response_model=EventResultsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get conjunction events",
    description="Retrieves close-approach conjunction events detected during a screening run, ordered by TCA ascending with pagination.",
    responses={
        200: {"description": "Paginated close-approach conjunction events.", "model": EventResultsResponse},
        404: {"description": "Run not found."},
        422: {"description": "Invalid pagination parameters."},
    },
)
def get_events(
    run_id: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of events to return (1-1000)"),
    offset: int = Query(default=0, ge=0, description="Number of events to skip for pagination (>= 0)"),
    db: Session = Depends(get_db),
    run_service: RunService = Depends(get_run_service),
) -> EventResultsResponse:
    """Retrieve close-approach conjunction events for a specific screening run."""
    try:
        return run_service.get_run_events_paginated(
            run_id=run_id,
            limit=limit,
            offset=offset,
            db=db,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RUN_NOT_FOUND", "message": f"Run '{run_id}' was not found."},
        )
    except Exception as exc:
        logger.error("Unexpected error retrieving events for run '%s': %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "EVENT_RETRIEVAL_ERROR", "message": str(exc)},
        )
