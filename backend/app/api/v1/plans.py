"""Mission plans and asynchronous planning run initiation endpoints (Phase P13).

The original D-DATO specification is authoritative.
Routes are thin controllers delegating orchestration and persistence to RunService.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repositories import PlanRepository
from app.schemas.plan import (
    PlanCreateRequest,
    PlanResponse,
    PlanRunAcceptedResponse,
    PlanRunListResponse,
)
from app.services.run_service import RunService, get_run_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=PlanRunAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create planning run",
    description="Creates a D-DATO planning request and queues asynchronous execution.",
    responses={
        202: {
            "description": "Planning run accepted and queued for background execution.",
            "model": PlanRunAcceptedResponse,
        },
        422: {"description": "Validation error in planning parameters envelope."},
        500: {"description": "Internal server error during plan creation or worker dispatch."},
    },
)
def create_plan_run(
    plan_in: PlanCreateRequest,
    db: Session = Depends(get_db),
    run_service: RunService = Depends(get_run_service),
) -> PlanRunAcceptedResponse:
    """Create a new mission plan and submit an asynchronous screening run to the background worker."""
    try:
        summary = run_service.create_and_submit_run(plan_in.model_dump(), db=db)
        # Reflect actual persisted status (which may be 'queued' or 'running' if worker picks up immediately)
        current_status = run_service.get_run_status(summary.run_id, db=db)
        return PlanRunAcceptedResponse(
            plan_id=summary.plan_id,
            run_id=summary.run_id,
            status=current_status.status,
            message=current_status.message or "Screening run queued for execution",
            created_at=summary.created_at,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create and submit planning run: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "PLAN_RUN_CREATION_FAILED", "message": str(exc)},
        )


@router.get(
    "/{plan_id}",
    response_model=PlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Get mission plan",
    description="Retrieves configuration and search parameters of a stored mission plan.",
    responses={
        200: {"description": "Mission plan parameters.", "model": PlanResponse},
        404: {"description": "Plan not found."},
    },
)
def get_plan(
    plan_id: str,
    db: Session = Depends(get_db),
) -> PlanResponse:
    """Retrieve details of a specific mission plan by its unique ID."""
    repo = PlanRepository(db)
    plan = repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PLAN_NOT_FOUND", "message": f"Plan '{plan_id}' was not found."},
        )
    return PlanResponse.model_validate(plan)


@router.get(
    "/{plan_id}/runs",
    response_model=PlanRunListResponse,
    status_code=status.HTTP_200_OK,
    summary="List plan runs",
    description="Retrieves all asynchronous screening runs associated with a mission plan, ordered newest first.",
    responses={
        200: {"description": "List of screening runs for the plan.", "model": PlanRunListResponse},
        404: {"description": "Plan not found."},
    },
)
def list_plan_runs(
    plan_id: str,
    db: Session = Depends(get_db),
    run_service: RunService = Depends(get_run_service),
) -> PlanRunListResponse:
    """Retrieve all screening runs linked to a specific mission plan."""
    repo = PlanRepository(db)
    plan = repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PLAN_NOT_FOUND", "message": f"Plan '{plan_id}' was not found."},
        )

    runs = run_service.list_runs(plan_id, db=db)
    return PlanRunListResponse(
        plan_id=plan_id,
        total=len(runs),
        runs=[r.to_response() for r in runs],
    )
