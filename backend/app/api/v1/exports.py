"""CSV and PDF export endpoints (Phase P17).

NON-OPERATIONAL POSITIONING:
D-DATO is an early-stage screening/planning aid. It is NOT a certified collision-probability
system, operational conjunction assessment tool, maneuver planner, CDM generator, or launch
COLA system. Exports are strictly read-only serialization over persisted database results.
No scientific recomputation, worker submission, or external network access is triggered.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.export_service import (
    ExportArtifact,
    ExportGenerationError,
    ExportService,
    RunNotFoundError,
    get_export_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{run_id}/exports/csv",
    response_class=Response,
    summary="Export run results as CSV ZIP archive",
    description=(
        "Exports persisted screening plan parameters, evaluated candidate orbits, "
        "close-approach conjunction events, and external validation comparison results "
        "(when available) as a structured ZIP archive containing typed CSV files. "
        "Strictly read-only; does NOT re-run screening, propagation, or validation."
    ),
    responses={
        200: {
            "description": "ZIP archive containing typed CSV files for the screening run.",
            "content": {
                "application/zip": {
                    "schema": {
                        "type": "string",
                        "format": "binary",
                    }
                }
            },
        },
        404: {
            "description": "Specified run_id not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "RUN_NOT_FOUND",
                            "message": "Run 'run-123' was not found.",
                        }
                    }
                }
            },
        },
        500: {
            "description": "Internal error occurred while generating CSV export.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "EXPORT_GENERATION_ERROR",
                            "message": "Failed to generate CSV export archive.",
                        }
                    }
                }
            },
        },
    },
)
@router.get(
    "/{run_id}/export/csv",
    include_in_schema=False,
)
def export_run_csv(
    run_id: str,
    db: Session = Depends(get_db),
    export_service: ExportService = Depends(get_export_service),
) -> Response:
    """Generate and download a ZIP archive containing separate CSV files for run_id."""
    try:
        artifact: ExportArtifact = export_service.export_csv(run_id=run_id, db=db)
        return Response(
            content=artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            },
        )
    except RunNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RUN_NOT_FOUND",
                "message": f"Run '{run_id}' was not found.",
            },
        )
    except ExportGenerationError as exc:
        logger.error("ExportGenerationError generating CSV for run '%s': %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "EXPORT_GENERATION_ERROR",
                "message": str(exc),
            },
        )
    except Exception as exc:
        logger.error("Unexpected error generating CSV export for run '%s': %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "EXPORT_GENERATION_ERROR",
                "message": "Failed to generate CSV export archive.",
            },
        )


@router.get(
    "/{run_id}/exports/pdf",
    response_class=Response,
    summary="Export run results as executive PDF screening report",
    description=(
        "Generates a multi-page PDF executive screening report containing run summary, "
        "planning constraints, ranked candidate orbits, close-approach events, "
        "external validation comparisons, and methodological scope notes. "
        "Strictly read-only; does NOT re-run screening, propagation, or validation."
    ),
    responses={
        200: {
            "description": "Executive screening PDF report for the run.",
            "content": {
                "application/pdf": {
                    "schema": {
                        "type": "string",
                        "format": "binary",
                    }
                }
            },
        },
        404: {
            "description": "Specified run_id not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "RUN_NOT_FOUND",
                            "message": "Run 'run-123' was not found.",
                        }
                    }
                }
            },
        },
        500: {
            "description": "Internal error occurred while generating PDF report.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "EXPORT_GENERATION_ERROR",
                            "message": "Failed to generate PDF screening report.",
                        }
                    }
                }
            },
        },
    },
)
@router.get(
    "/{run_id}/export/pdf",
    include_in_schema=False,
)
def export_run_pdf(
    run_id: str,
    db: Session = Depends(get_db),
    export_service: ExportService = Depends(get_export_service),
) -> Response:
    """Generate and download a PDF executive screening report for run_id."""
    try:
        artifact: ExportArtifact = export_service.export_pdf(run_id=run_id, db=db)
        return Response(
            content=artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            },
        )
    except RunNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RUN_NOT_FOUND",
                "message": f"Run '{run_id}' was not found.",
            },
        )
    except ExportGenerationError as exc:
        logger.error("ExportGenerationError generating PDF for run '%s': %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "EXPORT_GENERATION_ERROR",
                "message": str(exc),
            },
        )
    except Exception as exc:
        logger.error("Unexpected error generating PDF report for run '%s': %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "EXPORT_GENERATION_ERROR",
                "message": "Failed to generate PDF screening report.",
            },
        )
