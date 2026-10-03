"""SQLAlchemy 2.x declarative ORM models for D-DATO.

The original D-DATO project specification is authoritative.
Models define normalized persistence structures for:
- Plan: User planning requests and constraint parameters
- Run: Asynchronous execution lifecycle tracking
- Candidate: Discretized deployment windows and calculated orbital metrics
- DebrisObject: Tracked space debris catalog entries with raw TLEs
- DataSnapshot: Ingestion cache metadata and data freshness metrics
- ConjunctionEvent: Screened close-approach encounters
- ValidationRecord: External validation comparisons (e.g. SOCRATES)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.utils.time import is_aware, now_utc


def generate_uuid() -> str:
    """Generate a standard UUID4 string for primary keys."""
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator):
    """Platform-independent DateTime ensuring timezone-aware UTC across SQLite and PostgreSQL."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        """Ensure input datetime is aware and normalized to UTC before persisting."""
        if value is not None:
            if not is_aware(value):
                raise ValueError(
                    f"Naive datetime {value} passed to database layer. All timestamps must be timezone-aware UTC."
                )
            return value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        """Restore explicit UTC timezone when loaded from dialects that strip tzinfo (such as SQLite)."""
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


class RunStatus(str, Enum):
    """Execution status states for asynchronous screening runs."""
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class SnapshotStatus(str, Enum):
    """Ingestion snapshot outcome statuses."""
    success = "success"
    failed = "failed"
    partial = "partial"


class Plan(Base):
    """Represents a user's mission planning request and input parameter envelope."""
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=now_utc, onupdate=now_utc, nullable=False
    )

    # Temporal deployment window start
    epoch_start: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    # Altitude grid search bounds (km)
    altitude_min_km: Mapped[float] = mapped_column(Float, nullable=False)
    altitude_max_km: Mapped[float] = mapped_column(Float, nullable=False)
    altitude_step_km: Mapped[float] = mapped_column(Float, nullable=False)

    # Inclination grid search bounds (deg)
    inclination_min_deg: Mapped[float] = mapped_column(Float, nullable=False)
    inclination_max_deg: Mapped[float] = mapped_column(Float, nullable=False)
    inclination_step_deg: Mapped[float] = mapped_column(Float, nullable=False)

    # Initial orbit angles (deg)
    raan_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    u0_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Deployment delay envelope (minutes)
    delay_min_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delay_max_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=720.0)
    delay_step_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)

    # RAAN delay coupling constant (deg / min)
    raan_delay_coupling_deg_per_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.25068)

    # Screening duration & reference parameters
    screening_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    reference_altitude_km: Mapped[float] = mapped_column(Float, nullable=False, default=550.0)
    reference_inclination_deg: Mapped[float] = mapped_column(Float, nullable=False, default=97.5)

    # Propulsion and spacecraft parameters
    dv_budget_m_s: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    spacecraft_mass_kg: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    isp_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)

    # Multi-objective weights (must sum to 1.0)
    fuel_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.4)
    risk_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)

    # Source & Execution modes
    data_source: Mapped[str] = mapped_column(String(32), nullable=False, default="celestrak")
    demo_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    runs: Mapped[List["Run"]] = relationship("Run", back_populates="plan", cascade="all, delete-orphan")

    @property
    def plan_id(self) -> str:
        """Alias property matching schema plan_id."""
        return self.id


class Run(Base):
    """Represents one asynchronous execution lifecycle of a mission plan."""
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RunStatus.queued.value)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    # Progress and status messaging
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan", back_populates="runs")
    candidates: Mapped[List["Candidate"]] = relationship(
        "Candidate", back_populates="run", cascade="all, delete-orphan"
    )
    conjunction_events: Mapped[List["ConjunctionEvent"]] = relationship(
        "ConjunctionEvent", back_populates="run", cascade="all, delete-orphan"
    )
    validation_records: Mapped[List["ValidationRecord"]] = relationship(
        "ValidationRecord", back_populates="run", cascade="all, delete-orphan"
    )


class Candidate(Base):
    """Represents one generated candidate deployment window and orbital insertion option."""
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    altitude_km: Mapped[float] = mapped_column(Float, nullable=False)
    inclination_deg: Mapped[float] = mapped_column(Float, nullable=False)
    raan_deg: Mapped[float] = mapped_column(Float, nullable=False)
    u0_deg: Mapped[float] = mapped_column(Float, nullable=False)
    deployment_delay_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_raan_deg: Mapped[float] = mapped_column(Float, nullable=False)

    # Fuel & Maneuver budgeting
    delta_v_m_s: Mapped[float] = mapped_column(Float, nullable=False)
    propellant_mass_kg: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    within_dv_budget: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Risk & Ranking
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, nullable=False)

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="candidates")
    conjunction_events: Mapped[List["ConjunctionEvent"]] = relationship(
        "ConjunctionEvent", back_populates="candidate", cascade="all, delete-orphan"
    )
    validation_records: Mapped[List["ValidationRecord"]] = relationship(
        "ValidationRecord", back_populates="candidate"
    )

    @property
    def candidate_id(self) -> str:
        """Alias property matching schema candidate_id."""
        return self.id


class DebrisObject(Base):
    """Represents a tracked space debris object or active satellite in the catalog.

    Supports both legacy Two-Line Elements (TLE) and modern Orbit Mean-Elements Message (OMM)
    formats (including 6-digit catalog numbers without legacy TLE representations).
    """
    __tablename__ = "debris_objects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    norad_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    object_name: Mapped[str] = mapped_column(String(128), nullable=False)
    object_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # International Designator
    classification: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Element format ("tle" or "omm")
    element_format: Mapped[str] = mapped_column(String(16), nullable=False, default="tle")

    # Raw Two-Line Element lines (nullable for modern 6-digit objects lacking legacy TLE)
    tle_line1: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    tle_line2: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    epoch: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)

    # Core Keplerian/SGP4 orbital elements
    inclination_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eccentricity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raan_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    arg_perigee_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mean_anomaly_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mean_motion_rev_per_day: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Perturbation and drag parameters
    bstar: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mean_motion_dot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mean_motion_ddot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ephemeris_type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    element_set_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rev_at_epoch: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Raw serialized payload (for full provenance without loss)
    raw_source_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ingestion provenance
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    data_age_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=now_utc, onupdate=now_utc, nullable=False
    )

    # Composite index for querying NORAD objects by catalog source
    __table_args__ = (
        Index("ix_debris_norad_source", "norad_id", "source"),
    )

    # Relationships
    conjunction_events: Mapped[List["ConjunctionEvent"]] = relationship(
        "ConjunctionEvent", back_populates="debris_object"
    )


class DataSnapshot(Base):
    """Represents a cached ingestion batch or fetch event capturing catalog freshness."""
    __tablename__ = "data_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    data_age_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    object_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SnapshotStatus.success.value)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, nullable=False)


class ConjunctionEvent(Base):
    """Represents a close-approach encounter detected between a candidate orbit and space debris."""
    __tablename__ = "conjunction_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=True, index=True
    )
    debris_object_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("debris_objects.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Conjunction geometry & parameters
    tca: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    miss_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    relative_velocity_km_s: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_km: Mapped[float] = mapped_column(Float, nullable=False)
    screening_source: Mapped[str] = mapped_column(String(64), nullable=False, default="ddato")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, nullable=False)

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="conjunction_events")
    candidate: Mapped[Optional["Candidate"]] = relationship("Candidate", back_populates="conjunction_events")
    debris_object: Mapped[Optional["DebrisObject"]] = relationship(
        "DebrisObject", back_populates="conjunction_events"
    )


class ValidationRecord(Base):
    """Represents external benchmark or comparison record (e.g. against SOCRATES or CelesTrak)."""
    __tablename__ = "validation_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True, index=True
    )

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    source_fetched_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    external_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_time: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, nullable=False)

    # Aggregate run-level comparison metrics (Phase P16)
    matched_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    d_dato_only_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    external_only_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    external_coverage_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d_dato_match_rate_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    comparison_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Legacy per-event comparison fields (retained for backward compatibility)
    measured_or_reference_miss_distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ddato_miss_distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    absolute_error_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relative_error_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, nullable=False)

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="validation_records")
    candidate: Mapped[Optional["Candidate"]] = relationship("Candidate", back_populates="validation_records")
