"""Pydantic schemas for Screening Runs."""

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class RunStatusEnum(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScreeningRunCreate(BaseModel):
    plan_id: str = Field(..., description="ID of mission plan to screen")
    coarse_threshold_km: float = Field(default=50.0, description="Coarse spatial filter distance threshold (km)")
    fine_threshold_km: float = Field(default=5.0, description="Fine conjunction alert threshold (km)")


class ScreeningRunResponse(BaseModel):
    id: str
    plan_id: str
    status: RunStatusEnum
    progress: float
    candidates_count: int
    conjunctions_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class RunStatusResponse(BaseModel):
    """Execution status and progress response for an asynchronous screening run (Phase P12)."""
    run_id: str = Field(..., description="Unique screening run identifier")
    plan_id: str = Field(..., description="Unique mission plan identifier")
    status: str = Field(..., description="Run lifecycle state (queued, running, completed, failed, cancelled)")
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Coarse stage progress percentage")
    current_stage: Optional[str] = Field(default=None, description="Active or last executed pipeline stage")
    message: Optional[str] = Field(default=None, description="Informational progress or stage message")
    created_at: datetime = Field(..., description="Creation epoch (UTC)")
    started_at: Optional[datetime] = Field(default=None, description="Execution start epoch (UTC)")
    completed_at: Optional[datetime] = Field(default=None, description="Execution completion/termination epoch (UTC)")
    error_message: Optional[str] = Field(default=None, description="Sanitized failure diagnostic message")
    candidate_count: int = Field(default=0, ge=0, description="Evaluated candidate count")
    conjunction_event_count: int = Field(default=0, ge=0, description="Detected close-approach conjunction event count")
    ranked_candidate_count: int = Field(default=0, ge=0, description="Ranked candidate count")

    model_config = ConfigDict(from_attributes=True)

