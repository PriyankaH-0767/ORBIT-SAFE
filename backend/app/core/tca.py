"""Time of Closest Approach (TCA) numerical refinement.

Implements Pass 2 of the D-DATO conjunction screening pipeline:
Bounded 1-D scalar numerical minimization of candidate-to-debris
spatial separation over a local time bracket identified during coarse screening.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Any, Callable, Optional, Tuple

import numpy as np
from scipy.optimize import minimize_scalar

from app.core.config import settings
from app.core.orbit import CircularJ2Orbit
from app.core.propagation import Sgp4Propagator, PropagationError
from app.utils.time import ensure_utc


class TCARefinementError(Exception):
    """Raised when numerical TCA refinement fails catastrophically."""
    pass


@dataclass(frozen=True)
class TCARefinementResult:
    """Immutable result of a numerical TCA refinement pass."""
    tca: datetime
    miss_distance_km: float
    relative_velocity_km_s: float
    success: bool
    iterations: int
    status_message: str


def refine_tca_scalar(
    distance_fn: Callable[[float], float],
    bracket_start: datetime,
    total_seconds: float,
    xtol_seconds: Optional[float] = None,
    max_iterations: Optional[int] = None,
) -> Tuple[datetime, float, bool, int, str]:
    """Pure mathematical bounded 1-D minimization of scalar distance function.

    Args:
        distance_fn: Callable taking elapsed seconds from bracket_start (float)
                     and returning separation in km.
        bracket_start: Timezone-aware UTC start of bracket.
        total_seconds: Duration of bracket in seconds (> 0).
        xtol_seconds: Absolute tolerance in seconds.
        max_iterations: Maximum optimizer iterations.

    Returns:
        Tuple of (tca, min_distance_km, success, iterations, status_message)
    """
    if total_seconds <= 0:
        tca = ensure_utc(bracket_start)
        d0 = distance_fn(0.0)
        return tca, float(d0), True, 0, "Zero-duration bracket evaluated at start"

    tol = xtol_seconds if xtol_seconds is not None else settings.SCREENING_TCA_XTOL_SECONDS
    max_iter = max_iterations if max_iterations is not None else settings.SCREENING_TCA_MAX_ITERATIONS

    def bounded_objective(s: float) -> float:
        s_clamped = max(0.0, min(float(s), total_seconds))
        val = distance_fn(s_clamped)
        if not math.isfinite(val):
            return 1e12
        return val

    res = minimize_scalar(
        bounded_objective,
        bounds=(0.0, total_seconds),
        method="bounded",
        options={"xatol": tol, "maxiter": max_iter},
    )

    opt_s = float(res.x)
    # Clamp to bracket strictly
    opt_s_clamped = max(0.0, min(opt_s, total_seconds))
    d_opt = distance_fn(opt_s_clamped)

    # Verify boundary endpoints directly
    d_start = distance_fn(0.0)
    d_end = distance_fn(total_seconds)

    if math.isfinite(d_start) and d_start <= d_opt:
        opt_s_clamped = 0.0
        min_dist = d_start
    elif math.isfinite(d_end) and d_end <= d_opt:
        opt_s_clamped = total_seconds
        min_dist = d_end
    else:
        min_dist = d_opt

    tca = ensure_utc(bracket_start + timedelta(seconds=opt_s_clamped))

    iterations = int(getattr(res, "nfev", 0) or getattr(res, "nit", 0))
    status_msg = str(getattr(res, "message", "Optimization terminated"))
    success = bool(res.success and math.isfinite(min_dist))

    # Fallback endpoint evaluation if optimization reported failure
    if not success:
        # Check endpoints and midpoint
        candidates = [0.0, 0.5 * total_seconds, total_seconds]
        evals = [(s, distance_fn(s)) for s in candidates]
        valid_evals = [(s, d) for s, d in evals if math.isfinite(d)]
        if valid_evals:
            best_s, best_d = min(valid_evals, key=lambda p: p[1])
            tca = ensure_utc(bracket_start + timedelta(seconds=best_s))
            min_dist = best_d
            status_msg = f"Optimizer failure fallback: evaluated endpoints/midpoint, best at +{best_s:.2f}s"

    return tca, float(min_dist), success, iterations, status_msg


def refine_tca(
    candidate_orbit: CircularJ2Orbit,
    debris_propagator: Sgp4Propagator,
    bracket_start: datetime,
    bracket_end: datetime,
    xtol_seconds: Optional[float] = None,
    max_iterations: Optional[int] = None,
) -> TCARefinementResult:
    """Refine Time of Closest Approach (TCA) for a candidate/debris pair over a time bracket.

    Args:
        candidate_orbit: CircularJ2Orbit anchored at candidate.deployment_epoch.
        debris_propagator: Sgp4Propagator initialized for the debris object.
        bracket_start: UTC timestamp for start of refinement interval.
        bracket_end: UTC timestamp for end of refinement interval.
        xtol_seconds: Optimizer convergence tolerance on time in seconds.
        max_iterations: Optimizer maximum iterations.

    Returns:
        TCARefinementResult with refined TCA, miss distance (km), relative speed (km/s),
        and convergence diagnostics.
    """
    start_utc = ensure_utc(bracket_start)
    end_utc = ensure_utc(bracket_end)

    if end_utc < start_utc:
        raise ValueError(
            f"bracket_end ({end_utc.isoformat()}) must be >= bracket_start ({start_utc.isoformat()})"
        )

    total_seconds = (end_utc - start_utc).total_seconds()

    # Pre-calculate candidate epoch offset to bracket_start in seconds
    cand_epoch_offset = (start_utc - candidate_orbit.epoch).total_seconds()

    def distance_at_offset(elapsed_seconds: float) -> float:
        t_current = start_utc + timedelta(seconds=elapsed_seconds)
        cand_dt = cand_epoch_offset + elapsed_seconds
        cand_pos, _ = candidate_orbit.state_at(cand_dt)
        deb_state = debris_propagator.propagate(t_current)
        deb_pos = deb_state.position_km

        dx = cand_pos[0] - deb_pos[0]
        dy = cand_pos[1] - deb_pos[1]
        dz = cand_pos[2] - deb_pos[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if not math.isfinite(dist):
            return 1e12
        return dist

    tca, _, success, iters, status_msg = refine_tca_scalar(
        distance_fn=distance_at_offset,
        bracket_start=start_utc,
        total_seconds=total_seconds,
        xtol_seconds=xtol_seconds,
        max_iterations=max_iterations,
    )

    # Independent post-minimization verification:
    # Recompute candidate and debris states at the exact derived TCA
    cand_dt_tca = (tca - candidate_orbit.epoch).total_seconds()
    cand_pos, cand_vel = candidate_orbit.state_at(cand_dt_tca)

    try:
        deb_state = debris_propagator.propagate(tca)
        deb_pos = deb_state.position_km
        deb_vel = deb_state.velocity_km_s
    except PropagationError as e:
        return TCARefinementResult(
            tca=tca,
            miss_distance_km=float("inf"),
            relative_velocity_km_s=0.0,
            success=False,
            iterations=iters,
            status_message=f"Independent state recomputation failed at TCA: {e}",
        )

    dx = cand_pos[0] - deb_pos[0]
    dy = cand_pos[1] - deb_pos[1]
    dz = cand_pos[2] - deb_pos[2]
    miss_distance_km = float(math.sqrt(dx * dx + dy * dy + dz * dz))

    dvx = cand_vel[0] - deb_vel[0]
    dvy = cand_vel[1] - deb_vel[1]
    dvz = cand_vel[2] - deb_vel[2]
    relative_velocity_km_s = float(math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz))

    if not (math.isfinite(miss_distance_km) and math.isfinite(relative_velocity_km_s)):
        return TCARefinementResult(
            tca=tca,
            miss_distance_km=float("inf"),
            relative_velocity_km_s=0.0,
            success=False,
            iterations=iters,
            status_message="Non-finite state vector encountered at TCA",
        )

    return TCARefinementResult(
        tca=tca,
        miss_distance_km=miss_distance_km,
        relative_velocity_km_s=relative_velocity_km_s,
        success=success,
        iterations=iters,
        status_message=status_msg,
    )
