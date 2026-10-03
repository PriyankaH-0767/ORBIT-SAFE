"""Pydantic schemas for health and system status."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response model for service health check."""

    status: str = Field(..., description="Service health status", examples=["ok"])
    service: str = Field(..., description="Application name", examples=["D-DATO"])
    version: str = Field(..., description="Application semantic version", examples=["0.1.0"])
    environment: str = Field(..., description="Deployment environment", examples=["development"])
