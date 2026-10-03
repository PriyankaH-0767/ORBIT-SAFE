"""Candidate deployment window and orbital insertion results endpoints (Phase P13).

The original D-DATO specification is authoritative.
Retrieves evaluated candidates ordered by rank ASC with database-level pagination.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.candidate import CandidateResultsResponse
from app.services.run_service import RunService, get_run_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{run_id}/candidates",
    response_model=CandidateResultsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ranked candidate orbits",
    description="Retrieves evaluated deployment window candidates for a screening run, ordered by rank ascending with pagination.",
    responses={
        200: {"description": "Paginated candidate orbit results.", "model": CandidateResultsResponse},
        404: {"description": "Run not found."},
        422: {"description": "Invalid pagination parameters."},
    },
)
def get_candidates(
    run_id: str,
    limit: int = Query(default=100, ge=1, le=300, description="Maximum number of candidates to return (1-300)"),
    offset: int = Query(default=0, ge=0, description="Number of candidates to skip for pagination (>= 0)"),
    db: Session = Depends(get_db),
    run_service: RunService = Depends(get_run_service),
) -> CandidateResultsResponse:
    """Retrieve ranked deployment candidates for a screening run."""
    try:
        return run_service.get_run_candidates_paginated(
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
        logger.error("Unexpected error retrieving candidates for run '%s': %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "CANDIDATE_RETRIEVAL_ERROR", "message": str(exc)},
        )
