"""3D globe trajectory visualization endpoints (Phase P15).

The original D-DATO specification is authoritative.

Exposes TEME-frame Cartesian trajectories for:
  - Ranked candidate deployment orbits (Circular J2 propagation)
  - Debris objects involved in screening (SGP4 propagation)
  - Conjunction event markers

Read-only endpoint: does NOT restart, rescreen, rerank, or trigger workers.
Offline endpoint: does NOT call CelesTrak or make network calls.
Frame: TEME. Position: km. Velocity: km/s.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.globe import GlobeResponse
from app.services.globe_service import (
    CandidateNotFoundError,
    GlobeService,
    RunNotFoundError,
    get_globe_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Query parameter bounds
_SAMPLE_STEP_MIN = 30     # 30 seconds minimum agreed bound
_SAMPLE_STEP_MAX = 3600   # 1 hour maximum
_MAX_CANDIDATES_CAP = 50
_MAX_DEBRIS_CAP = 100


@router.get(
    "/{run_id}/globe",
    response_model=GlobeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get 3D globe trajectory data",
    description=(
        "Retrieves TEME-frame Cartesian orbital trajectories for ranked candidate orbits "
        "and associated debris objects in a D-DATO screening run, plus conjunction event markers. "
        "Strictly read-only and offline. Frame: TEME. Position: km. Velocity: km/s."
    ),
    responses={
        200: {
            "description": "Globe trajectory data successfully retrieved.",
            "model": GlobeResponse,
        },
        404: {
            "description": "Run or requested candidate not found.",
        },
        422: {
            "description": "Invalid query parameters.",
        },
        500: {
            "description": "Internal server error retrieving globe data.",
        },
    },
)
def get_globe_data(
    run_id: str,
    candidate_ids: Optional[str] = Query(
        default=None,
        description=(
            "Optional comma-separated candidate database IDs to visualize. "
            "If provided, returns only these candidates (must belong to the run). "
            "If omitted, returns top-ranked candidates up to max_candidates."
        ),
    ),
    sample_step_seconds: int = Query(
        default=300,
        ge=_SAMPLE_STEP_MIN,
        le=_SAMPLE_STEP_MAX,
        description=(
            f"Trajectory sampling interval in seconds "
            f"({_SAMPLE_STEP_MIN}–{_SAMPLE_STEP_MAX}). Default 300."
        ),
    ),
    max_candidates: int = Query(
        default=20,
        ge=1,
        le=_MAX_CANDIDATES_CAP,
        description=(
            f"Maximum number of candidate tracks to return "
            f"(1–{_MAX_CANDIDATES_CAP}). Ordered by rank ASC. Default 20."
        ),
    ),
    max_debris: int = Query(
        default=25,
        ge=1,
        le=_MAX_DEBRIS_CAP,
        description=(
            f"Maximum number of debris tracks to return "
            f"(1–{_MAX_DEBRIS_CAP}). Prioritizes debris from events. Default 25."
        ),
    ),
    db: Session = Depends(get_db),
    globe_service: GlobeService = Depends(get_globe_service),
) -> GlobeResponse:
    """Retrieve TEME-frame 3D orbital trajectory data for a screening run."""
    parsed_candidate_ids: Optional[list[str]] = None
    if candidate_ids is not None:
        trimmed = candidate_ids.strip()
        if not trimmed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "INVALID_CANDIDATE_IDS",
                    "message": "candidate_ids parameter cannot be empty when provided.",
                },
            )
        parts = [p.strip() for p in candidate_ids.split(",")]
        if any(not p for p in parts):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "INVALID_CANDIDATE_IDS",
                    "message": "candidate_ids contains empty or malformed identifier.",
                },
            )
        seen = set()
        parsed_candidate_ids = [p for p in parts if not (p in seen or seen.add(p))]

    try:
        return globe_service.get_globe_data(
            run_id=run_id,
            candidate_ids=parsed_candidate_ids,
            sample_step_seconds=sample_step_seconds,
            max_candidates=max_candidates,
            max_debris=max_debris,
            db=db,
        )
    except RunNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RUN_NOT_FOUND",
                "message": f"Run '{run_id}' was not found.",
            },
        )
    except CandidateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "CANDIDATE_NOT_FOUND",
                "message": f"Candidate '{exc.candidate_id}' was not found for run '{exc.run_id}'.",
            },
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "NOT_FOUND",
                    "message": msg,
                },
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_ARGUMENT",
                "message": msg,
            },
        )
    except Exception as exc:
        logger.error(
            "Unexpected error retrieving globe data for run '%s': %s", run_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "GLOBE_RETRIEVAL_ERROR",
                "message": str(exc),
            },
        )
