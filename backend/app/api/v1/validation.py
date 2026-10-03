"""External conjunction validation API endpoints (Phase P16).

The original D-DATO specification is authoritative.

NON-OPERATIONAL POSITIONING:
Validation compares D-DATO conjunction screening outputs against external reference
sources (specifically SOCRATES). It is external reference evidence only and does NOT
represent certified flight safety, operational conjunction assessment, true collision
probability, CDM generation, maneuver planning, or launch COLA.

Exposes:
- POST /api/v1/runs/{run_id}/validation: Execute validation comparison and persist report
- GET  /api/v1/runs/{run_id}/validation: Retrieve latest persisted validation report for a run
- GET  /api/v1/validations/{validation_id}: Retrieve persisted validation report by ID
"""

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.data.socrates import (
    ValidationSourceError,
    ValidationSourceUnavailableError,
)
from app.db.database import get_db
from app.schemas.validation import (
    ValidationExecutionRequest,
    ValidationResponse,
)
from app.services.validation_service import (
    InvalidValidationRequestError,
    RunNotFoundError,
    ValidationNotFoundError,
    ValidationService,
    get_validation_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/runs/{run_id}/validation",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate run against external reference source",
    description=(
        "Executes a deterministic comparison between persisted D-DATO conjunction events "
        "and an external validation source (specifically SOCRATES). Produces matched pairs, "
        "discrepancies, and aggregate descriptive metrics. Strictly non-operational reference evidence."
    ),
    responses={
        200: {
            "description": "Validation successfully executed and persisted.",
            "model": ValidationResponse,
        },
        404: {
            "description": "Specified run_id not found.",
        },
        422: {
            "description": "Invalid validation request parameters or unsupported source.",
        },
        503: {
            "description": "External validation source unavailable and no cache/fixture exists.",
        },
    },
)
def validate_run(
    run_id: str,
    payload: ValidationExecutionRequest = Body(default_factory=ValidationExecutionRequest),
    db: Session = Depends(get_db),
    validation_service: ValidationService = Depends(get_validation_service),
) -> ValidationResponse:
    """Validate persisted conjunction events for a run against an external reference source."""
    try:
        return validation_service.validate_run(
            run_id=run_id,
            request=payload,
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
    except (InvalidValidationRequestError, ValidationSourceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_VALIDATION_REQUEST",
                "message": str(exc),
            },
        )
    except ValidationSourceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "VALIDATION_SOURCE_UNAVAILABLE",
                "message": str(exc),
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_VALIDATION_REQUEST",
                "message": str(exc),
            },
        )
    except Exception as exc:
        logger.error("Unexpected error validating run '%s': %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "VALIDATION_RETRIEVAL_ERROR",
                "message": "Internal error occurred while processing validation request.",
            },
        )


@router.get(
    "/runs/{run_id}/validation",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest validation report for a run",
    description=(
        "Retrieves the most recent persisted validation report for a screening run. "
        "Strictly read-only; does NOT re-run screening or external validation queries."
    ),
    responses={
        200: {
            "description": "Persisted validation report successfully retrieved.",
            "model": ValidationResponse,
        },
        404: {
            "description": "Run or validation record not found.",
        },
    },
)
def get_latest_validation(
    run_id: str,
    db: Session = Depends(get_db),
    validation_service: ValidationService = Depends(get_validation_service),
) -> ValidationResponse:
    """Retrieve the latest persisted validation report for a screening run."""
    try:
        return validation_service.get_latest_validation_for_run(
            run_id=run_id,
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
    except ValidationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "VALIDATION_NOT_FOUND",
                "message": str(exc),
            },
        )
    except Exception as exc:
        logger.error("Unexpected error retrieving validation for run '%s': %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "VALIDATION_RETRIEVAL_ERROR",
                "message": "Internal error occurred while retrieving validation record.",
            },
        )


@router.get(
    "/validations/{validation_id}",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get validation report by ID",
    description=(
        "Directly retrieves a specific persisted validation report by its unique identifier. "
        "Strictly read-only."
    ),
    responses={
        200: {
            "description": "Validation report successfully retrieved.",
            "model": ValidationResponse,
        },
        404: {
            "description": "Validation record not found.",
        },
    },
)
def get_validation_by_id(
    validation_id: str,
    db: Session = Depends(get_db),
    validation_service: ValidationService = Depends(get_validation_service),
) -> ValidationResponse:
    """Retrieve a specific persisted validation report by its ID."""
    try:
        return validation_service.get_validation_by_id(
            validation_id=validation_id,
            db=db,
        )
    except ValidationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "VALIDATION_NOT_FOUND",
                "message": str(exc),
            },
        )
    except Exception as exc:
        logger.error("Unexpected error retrieving validation '%s': %s", validation_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "VALIDATION_RETRIEVAL_ERROR",
                "message": "Internal error occurred while retrieving validation record.",
            },
        )
