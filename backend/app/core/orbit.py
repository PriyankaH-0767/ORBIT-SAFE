"""Orbital representations, classical Keplerian mechanics, and D-DATO Circular J2 model.

Authoritative Specification:
- Pure Python numerical formulations independent of frameworks (FastAPI/SQLAlchemy).
- Authoritative physical constants (MU, RE, J2) from app.core.constants.
- Circular J2 secular candidate orbit model for D-DATO screening.
- Rotation sequence: R3(Omega) * R1(i) to TEME-style inertial coordinates.
- Velocity derived analytically including secular nodal precession.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Optional, Tuple

from app.core.constants import DEG_TO_RAD, J2, MU, RAD_TO_DEG, RE
from app.utils.time import ensure_utc, is_aware, now_utc


@dataclass(frozen=True)
class KeplerianElements:
    """Classical Keplerian orbital elements (angles in radians for internal math)."""
    semi_major_axis_km: float
    eccentricity: float
    inclination_rad: float
    raan_rad: float
    arg_perigee_rad: float
    true_anomaly_rad: float

    @property
    def inclination_deg(self) -> float:
        return self.inclination_rad * RAD_TO_DEG

    @property
    def raan_deg(self) -> float:
        return self.raan_rad * RAD_TO_DEG

    @property
    def arg_perigee_deg(self) -> float:
        return self.arg_perigee_rad * RAD_TO_DEG

    @property
    def true_anomaly_deg(self) -> float:
        return self.true_anomaly_rad * RAD_TO_DEG

    @property
    def period_seconds(self) -> float:
        """Orbital period in seconds: T = 2*pi * sqrt(a^3 / mu)."""
        if self.semi_major_axis_km <= 0:
            return 0.0
        return 2.0 * math.pi * math.sqrt(math.pow(self.semi_major_axis_km, 3) / MU)


@dataclass(frozen=True)
class CircularJ2Orbit:
    """Analytical candidate orbit model under J2 Earth oblateness perturbation.

    Assumes a circular orbit (e = 0, p = a), where:
    - a = RE + altitude_km
    - Mean motion: n = sqrt(MU / a^3) (rad/s)
    - Secular RAAN precession rate:
        Omega_dot = -(3/2) * J2 * n * (RE/a)^2 * cos(i)
    - Secular argument of perigee rate:
        omega_dot = (3/4) * J2 * n * (RE/a)^2 * (5*cos^2(i) - 1)
    - Secular argument of latitude rate:
        u_dot = n + omega_dot
    - Position is transformed via R3(Omega(t)) * R1(i) to TEME Cartesian frame.
    - Velocity is derived analytically as d[r(t)]/dt including nodal precession.
    """

    altitude_km: float
    inclination_rad: float
    raan_rad: float
    u0_rad: float
    epoch: datetime

    semi_major_axis_km: float
    mean_motion_rad_s: float
    raan_rate_rad_s: float
    argument_of_latitude_rate_rad_s: float

    def __post_init__(self) -> None:
        """Validate input parameters."""
        if self.altitude_km <= 0:
            raise ValueError(f"altitude_km must be positive, got {self.altitude_km}")
        if not (0.0 <= self.inclination_rad <= math.pi):
            raise ValueError(f"inclination_rad must be in [0, pi], got {self.inclination_rad}")
        if not is_aware(self.epoch):
            raise ValueError("epoch must be a timezone-aware UTC datetime")
        for val_name, val in [
            ("semi_major_axis_km", self.semi_major_axis_km),
            ("mean_motion_rad_s", self.mean_motion_rad_s),
            ("raan_rate_rad_s", self.raan_rate_rad_s),
            ("argument_of_latitude_rate_rad_s", self.argument_of_latitude_rate_rad_s),
        ]:
            if not math.isfinite(val):
                raise ValueError(f"{val_name} must be finite, got {val}")

    @property
    def inclination_deg(self) -> float:
        return self.inclination_rad * RAD_TO_DEG

    @property
    def raan_deg(self) -> float:
        return self.raan_rad * RAD_TO_DEG

    @property
    def u0_deg(self) -> float:
        return self.u0_rad * RAD_TO_DEG

    @property
    def period_seconds(self) -> float:
        """Nodal orbital period in seconds: T = 2*pi / u_dot."""
        return 2.0 * math.pi / self.argument_of_latitude_rate_rad_s

    @property
    def period_minutes(self) -> float:
        return self.period_seconds / 60.0

    def position_at(self, dt_seconds: float) -> Tuple[float, float, float]:
        """Compute TEME Cartesian position (x, y, z) in km at elapsed time dt_seconds."""
        omega_t = self.raan_rad + self.raan_rate_rad_s * dt_seconds
        u_t = self.u0_rad + self.argument_of_latitude_rate_rad_s * dt_seconds

        cos_o = math.cos(omega_t)
        sin_o = math.sin(omega_t)
        cos_u = math.cos(u_t)
        sin_u = math.sin(u_t)
        cos_i = math.cos(self.inclination_rad)
        sin_i = math.sin(self.inclination_rad)

        a = self.semi_major_axis_km
        # Analytical R3(Omega) * R1(i) rotation of [a*cos(u), a*sin(u), 0]
        x = a * (cos_o * cos_u - sin_o * sin_u * cos_i)
        y = a * (sin_o * cos_u + cos_o * sin_u * cos_i)
        z = a * (sin_u * sin_i)
        return (x, y, z)

    def velocity_at(self, dt_seconds: float) -> Tuple[float, float, float]:
        """Compute TEME Cartesian velocity (vx, vy, vz) in km/s at elapsed time dt_seconds.

        Derived analytically as d[r(t)]/dt:
        v(t) = R3(Omega) R1(i) v_orb + Omega_dot * (k_hat x r(t))
        where v_orb = [-a*u_dot*sin(u), a*u_dot*cos(u), 0]^T.
        """
        omega_t = self.raan_rad + self.raan_rate_rad_s * dt_seconds
        u_t = self.u0_rad + self.argument_of_latitude_rate_rad_s * dt_seconds

        cos_o = math.cos(omega_t)
        sin_o = math.sin(omega_t)
        cos_u = math.cos(u_t)
        sin_u = math.sin(u_t)
        cos_i = math.cos(self.inclination_rad)
        sin_i = math.sin(self.inclination_rad)

        a = self.semi_major_axis_km
        u_dot = self.argument_of_latitude_rate_rad_s
        omega_dot = self.raan_rate_rad_s

        # Position components
        x = a * (cos_o * cos_u - sin_o * sin_u * cos_i)
        y = a * (sin_o * cos_u + cos_o * sin_u * cos_i)

        # Orbital plane velocity transformed to inertial frame
        v_rel_x = -u_dot * a * (cos_o * sin_u + sin_o * cos_u * cos_i)
        v_rel_y = u_dot * a * (cos_o * cos_u * cos_i - sin_o * sin_u)
        v_rel_z = a * u_dot * cos_u * sin_i

        # Add nodal precession cross-product contribution: Omega_dot * (k_hat x r) = [-Omega_dot*y, Omega_dot*x, 0]
        vx = v_rel_x - omega_dot * y
        vy = v_rel_y + omega_dot * x
        vz = v_rel_z
        return (vx, vy, vz)

    def state_at(self, dt_seconds: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Return position and velocity simultaneously at elapsed time dt_seconds."""
        return self.position_at(dt_seconds), self.velocity_at(dt_seconds)


def create_circular_j2_orbit(
    altitude_km: float,
    inclination_deg: float,
    raan_deg: float = 0.0,
    u0_deg: float = 0.0,
    epoch: Optional[datetime] = None,
) -> CircularJ2Orbit:
    """Factory creating and initializing a validated CircularJ2Orbit model.

    Formulas:
    - a = RE + altitude_km
    - n = sqrt(MU / a^3)
    - Omega_dot = -(3/2) * J2 * n * (RE / a)^2 * cos(i)
    - omega_dot = (3/4) * J2 * n * (RE / a)^2 * (5*cos^2(i) - 1)
    - u_dot = n + omega_dot
    """
    if altitude_km <= 0:
        raise ValueError(f"altitude_km must be > 0 (got {altitude_km})")
    if not (0.0 <= inclination_deg <= 180.0):
        raise ValueError(f"inclination_deg must be in [0, 180] (got {inclination_deg})")

    dt_epoch = ensure_utc(epoch) if epoch is not None else now_utc()

    inc_rad = inclination_deg * DEG_TO_RAD
    raan_rad = raan_deg * DEG_TO_RAD
    u0_rad = u0_deg * DEG_TO_RAD

    a = RE + altitude_km
    n = math.sqrt(MU / math.pow(a, 3))

    re_over_a = RE / a
    re_over_a_sq = re_over_a * re_over_a
    cos_i = math.cos(inc_rad)

    # Secular rates (rad / s)
    raan_rate = -1.5 * J2 * n * re_over_a_sq * cos_i
    arg_perigee_rate = 0.75 * J2 * n * re_over_a_sq * (5.0 * cos_i * cos_i - 1.0)
    u_rate = n + arg_perigee_rate

    return CircularJ2Orbit(
        altitude_km=altitude_km,
        inclination_rad=inc_rad,
        raan_rad=raan_rad,
        u0_rad=u0_rad,
        epoch=dt_epoch,
        semi_major_axis_km=a,
        mean_motion_rad_s=n,
        raan_rate_rad_s=raan_rate,
        argument_of_latitude_rate_rad_s=u_rate,
    )


def keplerian_to_cartesian(
    elements: KeplerianElements,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Convert classical Keplerian elements to Cartesian (r, v) state in orbital frame.

    Standard two-body conversion.
    """
    a = elements.semi_major_axis_km
    e = elements.eccentricity
    i = elements.inclination_rad
    raan = elements.raan_rad
    omega = elements.arg_perigee_rad
    nu = elements.true_anomaly_rad

    p = a * (1.0 - e * e)
    r_mag = p / (1.0 + e * math.cos(nu))

    # Perifocal position and velocity
    r_peri = (r_mag * math.cos(nu), r_mag * math.sin(nu), 0.0)
    v_coef = math.sqrt(MU / p)
    v_peri = (-v_coef * math.sin(nu), v_coef * (e + math.cos(nu)), 0.0)

    # Rotation matrix 3-1-3 (Omega, i, omega)
    cos_o, sin_o = math.cos(raan), math.sin(raan)
    cos_i, sin_i = math.cos(i), math.sin(i)
    cos_w, sin_w = math.cos(omega), math.sin(omega)

    P1 = (cos_o * cos_w - sin_o * sin_w * cos_i, -cos_o * sin_w - sin_o * cos_w * cos_i, sin_o * sin_i)
    P2 = (sin_o * cos_w + cos_o * sin_w * cos_i, -sin_o * sin_w + cos_o * cos_w * cos_i, -cos_o * sin_i)
    P3 = (sin_w * sin_i, cos_w * sin_i, cos_i)

    def _rot(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
        rx = P1[0] * v[0] + P1[1] * v[1] + P1[2] * v[2]
        ry = P2[0] * v[0] + P2[1] * v[1] + P2[2] * v[2]
        rz = P3[0] * v[0] + P3[1] * v[1] + P3[2] * v[2]
        return (rx, ry, rz)

    return _rot(r_peri), _rot(v_peri)
