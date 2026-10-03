"""Pydantic schemas for Debris Objects."""

from pydantic import BaseModel
from datetime import datetime


class DebrisObjectResponse(BaseModel):
    norad_id: str
    name: str
    line1: str
    line2: str
    epoch: datetime

    class Config:
        from_attributes = True


class TLEIngestRequest(BaseModel):
    source: str  # celestrak, spacetrack, local_demo
    group_or_filter: str
