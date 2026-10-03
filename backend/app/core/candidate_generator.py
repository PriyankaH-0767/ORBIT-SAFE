"""Candidate orbit and deployment window generator for D-DATO.

Phase P6: Deterministically generates candidate orbit options from planning
ranges, combining altitude, inclination, and deployment-delay dimensions,
with derived RAAN-delay coupling.

The original D-DATO project specification is authoritative.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import math
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.utils.time import ensure_utc, now_utc


class CandidateGenerationError(ValueError):
    """Raised when candidate generation violates physical, domain, or computational limits."""
    pass


@dataclass(frozen=True)
class CandidateOrbit:
    """Pure domain-level representation of a candidate deployment orbit and epoch.

    Decoupled from SQLAlchemy ORM and HTTP schemas.
    """
    candidate_id: str
    altitude_km: float
    inclination_deg: float
    raan_deg: float
    u0_deg: float
    deployment_delay_minutes: float
    base_raan_deg: float
    raan_delay_coupling_deg_per_min: float
    epoch_start: datetime
    deployment_epoch: datetime
    generated_index: int = 0

    @property
    def predicted_raan_deg(self) -> float:
        """Alias for derived raan_deg for backwards/schema compatibility."""
        return self.raan_deg


@dataclass(frozen=True)
class CandidateGenerationConfig:
    """Domain planning configuration parameters for candidate grid generation."""
    epoch_start: datetime
    altitude_min_km: float = settings.ALTITUDE_MIN_KM
    altitude_max_km: float = settings.ALTITUDE_MAX_KM
    altitude_step_km: float = settings.ALTITUDE_STEP_KM
    inclination_min_deg: float = settings.INCLINATION_MIN_DEG
    inclination_max_deg: float = settings.INCLINATION_MAX_DEG
    inclination_step_deg: float = settings.INCLINATION_STEP_DEG
    delay_min_minutes: float = settings.DELAY_MIN_MINUTES
    delay_max_minutes: float = settings.DELAY_MAX_MINUTES
    delay_step_minutes: float = settings.DELAY_STEP_MINUTES
    base_raan_deg: float = settings.RAAN_DEG
    u0_deg: float = settings.U0_DEG
    raan_delay_coupling_deg_per_min: float = settings.RAAN_DELAY_COUPLING_DEG_PER_MIN
    max_candidates: int = settings.MAX_CANDIDATES


def normalize_angle_360(angle_deg: float) -> float:
    """Normalize an angle in degrees into the half-open interval [0.0, 360.0)."""
    if not math.isfinite(angle_deg):
        raise CandidateGenerationError(f"Angle must be a finite number, got {angle_deg}")

    normalized = angle_deg % 360.0
    if normalized < 0.0:
        normalized += 360.0

    normalized = round(normalized, 8)
    if normalized >= 360.0 or normalized == 0.0 or abs(normalized) < 1e-12:
        normalized = 0.0

    return float(normalized)


def generate_grid(min_val: float, max_val: float, step: float) -> List[float]:
    """Generate a 1D discrete grid of numbers from min_val to max_val with step.

    Inclusive of endpoints when reached. Numerically stable using Decimal arithmetic
    to prevent floating-point accumulation drift (e.g. 97.4999999997).
    """
    if not (math.isfinite(min_val) and math.isfinite(max_val) and math.isfinite(step)):
        raise CandidateGenerationError(
            f"Grid bounds and step must be finite numbers (min={min_val}, max={max_val}, step={step})."
        )
    if step <= 0:
        raise CandidateGenerationError(f"Grid step must be strictly positive, got {step}.")
    if min_val > max_val:
        raise CandidateGenerationError(
            f"Grid min_val ({min_val}) cannot exceed max_val ({max_val})."
        )

    d_min = Decimal(str(min_val))
    d_max = Decimal(str(max_val))
    d_step = Decimal(str(step))

    # Number of steps: floor((max - min) / step + epsilon)
    # Using 1e-12 epsilon to tolerate minor representation rounding
    n_steps = int(((d_max - d_min) / d_step) + Decimal("1e-12"))

    values: List[float] = []
    for i in range(n_steps + 1):
        val = d_min + (Decimal(i) * d_step)
        if val <= d_max + Decimal("1e-12"):
            values.append(round(float(val), 8))

    return values


def generate_candidate_id(
    altitude_km: float,
    inclination_deg: float,
    delay_minutes: float,
) -> str:
    """Generate a deterministic, reconstructible candidate identifier string.

    Format: ALT{alt}_INC{inc}_DELAY{delay}
    Example: ALT500_INC97.0_DELAY000
    """
    alt_str = str(int(altitude_km)) if altitude_km.is_integer() else f"{altitude_km:g}"
    inc_str = f"{inclination_deg:.1f}" if round(inclination_deg, 1) == inclination_deg else f"{inclination_deg:g}"
    delay_str = f"{int(delay_minutes):03d}" if delay_minutes.is_integer() else f"{delay_minutes:g}"
    return f"ALT{alt_str}_INC{inc_str}_DELAY{delay_str}"


def generate_candidates(
    config: Optional[CandidateGenerationConfig] = None,
    *,
    epoch_start: Optional[datetime] = None,
    altitude_min_km: Optional[float] = None,
    altitude_max_km: Optional[float] = None,
    altitude_step_km: Optional[float] = None,
    inclination_min_deg: Optional[float] = None,
    inclination_max_deg: Optional[float] = None,
    inclination_step_deg: Optional[float] = None,
    delay_min_minutes: Optional[float] = None,
    delay_max_minutes: Optional[float] = None,
    delay_step_minutes: Optional[float] = None,
    base_raan_deg: Optional[float] = None,
    u0_deg: Optional[float] = None,
    raan_delay_coupling_deg_per_min: Optional[float] = None,
    max_candidates: Optional[int] = None,
) -> List[CandidateOrbit]:
    """Deterministically generate candidate orbit options from planning parameters.

    Iterates over the Cartesian product:
      altitude (ascending) -> inclination (ascending) -> deployment delay (ascending)

    Derives RAAN using the configured RAAN-delay coupling:
      predicted_raan = (base_raan + coupling * delay) % 360.0

    Derives deployment epoch:
      deployment_epoch = epoch_start + timedelta(minutes=delay)

    Strictly enforces maximum candidate limit (MAX_CANDIDATES = 300 default).
    Raises CandidateGenerationError if candidate count exceeds max_candidates.
    """
    # Resolve parameters from config or defaults
    if config is not None:
        cfg_epoch = epoch_start if epoch_start is not None else config.epoch_start
        cfg_alt_min = altitude_min_km if altitude_min_km is not None else config.altitude_min_km
        cfg_alt_max = altitude_max_km if altitude_max_km is not None else config.altitude_max_km
        cfg_alt_step = altitude_step_km if altitude_step_km is not None else config.altitude_step_km
        cfg_inc_min = inclination_min_deg if inclination_min_deg is not None else config.inclination_min_deg
        cfg_inc_max = inclination_max_deg if inclination_max_deg is not None else config.inclination_max_deg
        cfg_inc_step = inclination_step_deg if inclination_step_deg is not None else config.inclination_step_deg
        cfg_delay_min = delay_min_minutes if delay_min_minutes is not None else config.delay_min_minutes
        cfg_delay_max = delay_max_minutes if delay_max_minutes is not None else config.delay_max_minutes
        cfg_delay_step = delay_step_minutes if delay_step_minutes is not None else config.delay_step_minutes
        cfg_base_raan = base_raan_deg if base_raan_deg is not None else config.base_raan_deg
        cfg_u0 = u0_deg if u0_deg is not None else config.u0_deg
        cfg_coupling = (
            raan_delay_coupling_deg_per_min
            if raan_delay_coupling_deg_per_min is not None
            else config.raan_delay_coupling_deg_per_min
        )
        cfg_max_candidates = max_candidates if max_candidates is not None else config.max_candidates
    else:
        cfg_epoch = (
            epoch_start
            if epoch_start is not None
            else now_utc() + timedelta(days=settings.EPOCH_START_OFFSET_DAYS)
        )
        cfg_alt_min = altitude_min_km if altitude_min_km is not None else settings.ALTITUDE_MIN_KM
        cfg_alt_max = altitude_max_km if altitude_max_km is not None else settings.ALTITUDE_MAX_KM
        cfg_alt_step = altitude_step_km if altitude_step_km is not None else settings.ALTITUDE_STEP_KM
        cfg_inc_min = inclination_min_deg if inclination_min_deg is not None else settings.INCLINATION_MIN_DEG
        cfg_inc_max = inclination_max_deg if inclination_max_deg is not None else settings.INCLINATION_MAX_DEG
        cfg_inc_step = inclination_step_deg if inclination_step_deg is not None else settings.INCLINATION_STEP_DEG
        cfg_delay_min = delay_min_minutes if delay_min_minutes is not None else settings.DELAY_MIN_MINUTES
        cfg_delay_max = delay_max_minutes if delay_max_minutes is not None else settings.DELAY_MAX_MINUTES
        cfg_delay_step = delay_step_minutes if delay_step_minutes is not None else settings.DELAY_STEP_MINUTES
        cfg_base_raan = base_raan_deg if base_raan_deg is not None else settings.RAAN_DEG
        cfg_u0 = u0_deg if u0_deg is not None else settings.U0_DEG
        cfg_coupling = (
            raan_delay_coupling_deg_per_min
            if raan_delay_coupling_deg_per_min is not None
            else settings.RAAN_DELAY_COUPLING_DEG_PER_MIN
        )
        cfg_max_candidates = max_candidates if max_candidates is not None else settings.MAX_CANDIDATES

    # 1. Validate epoch
    aware_epoch = ensure_utc(cfg_epoch)

    # 2. Validate altitude range
    if cfg_alt_min <= 0 or cfg_alt_max <= 0:
        raise CandidateGenerationError(
            f"Altitude bounds must be positive numbers (got min={cfg_alt_min}, max={cfg_alt_max})."
        )
    if cfg_alt_min > cfg_alt_max:
        raise CandidateGenerationError(
            f"altitude_min_km ({cfg_alt_min}) cannot exceed altitude_max_km ({cfg_alt_max})."
        )
    if cfg_alt_step <= 0:
        raise CandidateGenerationError(f"altitude_step_km ({cfg_alt_step}) must be > 0.")

    # 3. Validate inclination range
    for name, val in [("inclination_min_deg", cfg_inc_min), ("inclination_max_deg", cfg_inc_max)]:
        if not (0.0 <= val <= 180.0):
            raise CandidateGenerationError(f"{name} ({val}) must be between 0.0 and 180.0 degrees.")
    if cfg_inc_min > cfg_inc_max:
        raise CandidateGenerationError(
            f"inclination_min_deg ({cfg_inc_min}) cannot exceed inclination_max_deg ({cfg_inc_max})."
        )
    if cfg_inc_step <= 0:
        raise CandidateGenerationError(f"inclination_step_deg ({cfg_inc_step}) must be > 0.")

    # 4. Validate delay range
    if cfg_delay_min < 0 or cfg_delay_max < 0:
        raise CandidateGenerationError(
            f"Delay bounds must be non-negative (got min={cfg_delay_min}, max={cfg_delay_max})."
        )
    if cfg_delay_min > cfg_delay_max:
        raise CandidateGenerationError(
            f"delay_min_minutes ({cfg_delay_min}) cannot exceed delay_max_minutes ({cfg_delay_max})."
        )
    if cfg_delay_step <= 0:
        raise CandidateGenerationError(f"delay_step_minutes ({cfg_delay_step}) must be > 0.")

    # 5. Validate angle and coupling parameters
    if not math.isfinite(cfg_base_raan):
        raise CandidateGenerationError(f"base_raan_deg must be finite, got {cfg_base_raan}.")
    if not math.isfinite(cfg_coupling):
        raise CandidateGenerationError(
            f"raan_delay_coupling_deg_per_min must be finite, got {cfg_coupling}."
        )
    if not math.isfinite(cfg_u0):
        raise CandidateGenerationError(f"u0_deg must be finite, got {cfg_u0}.")
    if cfg_max_candidates <= 0:
        raise CandidateGenerationError(f"max_candidates must be > 0, got {cfg_max_candidates}.")

    # Generate 1D grids
    altitude_grid = generate_grid(cfg_alt_min, cfg_alt_max, cfg_alt_step)
    inclination_grid = generate_grid(cfg_inc_min, cfg_inc_max, cfg_inc_step)
    delay_grid = generate_grid(cfg_delay_min, cfg_delay_max, cfg_delay_step)

    # 6. Check total candidate count against maximum limit
    total_candidates = len(altitude_grid) * len(inclination_grid) * len(delay_grid)
    if total_candidates > cfg_max_candidates:
        raise CandidateGenerationError(
            f"requested grid produces {total_candidates} candidates (altitudes={len(altitude_grid)}, "
            f"inclinations={len(inclination_grid)}, delays={len(delay_grid)}); "
            f"maximum is {cfg_max_candidates}."
        )

    # 7. Generate candidates in deterministic order
    # ascending altitude -> ascending inclination -> ascending delay
    normalized_base_raan = normalize_angle_360(cfg_base_raan)
    candidates: List[CandidateOrbit] = []
    idx = 0

    for alt in altitude_grid:
        for inc in inclination_grid:
            for delay in delay_grid:
                derived_raan = normalize_angle_360(
                    normalized_base_raan + (cfg_coupling * delay)
                )
                dep_epoch = aware_epoch + timedelta(minutes=delay)
                cand_id = generate_candidate_id(alt, inc, delay)

                cand = CandidateOrbit(
                    candidate_id=cand_id,
                    altitude_km=alt,
                    inclination_deg=inc,
                    raan_deg=derived_raan,
                    u0_deg=cfg_u0,
                    deployment_delay_minutes=delay,
                    base_raan_deg=normalized_base_raan,
                    raan_delay_coupling_deg_per_min=cfg_coupling,
                    epoch_start=aware_epoch,
                    deployment_epoch=dep_epoch,
                    generated_index=idx,
                )
                candidates.append(cand)
                idx += 1

    return candidates


def candidate_to_model_data(
    candidate: CandidateOrbit,
    run_id: Optional[str] = None,
    estimate: Optional[Any] = None,
) -> Dict[str, Any]:
    """Convert a pure domain CandidateOrbit and optional DeltaVEstimate into a dictionary suitable for SQLAlchemy Candidate persistence.

    Does NOT persist, commit, or touch database sessions.
    """
    data: Dict[str, Any] = {
        "run_id": run_id or "",
        "altitude_km": candidate.altitude_km,
        "inclination_deg": candidate.inclination_deg,
        "raan_deg": candidate.raan_deg,
        "u0_deg": candidate.u0_deg,
        "deployment_delay_minutes": candidate.deployment_delay_minutes,
        "predicted_raan_deg": candidate.raan_deg,
    }
    if estimate is not None:
        data.update({
            "delta_v_m_s": getattr(estimate, "total_dv_m_s", 0.0),
            "propellant_mass_kg": getattr(estimate, "propellant_mass_kg", 0.0),
            "fuel_fraction": getattr(estimate, "fuel_fraction", 0.0),
            "within_dv_budget": getattr(estimate, "within_dv_budget", True),
        })
    return data
