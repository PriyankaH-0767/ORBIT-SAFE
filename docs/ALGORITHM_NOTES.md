# D-DATO Astrodynamics & Algorithm Notes

## 0. D-DATO Scientific Conventions

> **The original D-DATO project specification is authoritative. These conventions must not be silently changed by implementation code.**

### 0.1 Authoritative Physical & Astrodynamic Constants
Defined centrally in `app.core.constants`:
- **$\mu$ (Earth Gravitational Parameter)**: $398600.4418 \text{ km}^3/\text{s}^2$
- **$R_E$ (Earth Equatorial Radius)**: $6378.137 \text{ km}$ (WGS-84 / EGM96 standard)
- **$J_2$ (Second Zonal Harmonic)**: $1.08262668 \times 10^{-3}$ (dimensionless)
- **$g_0$ (Standard Gravity)**: $9.80665 \text{ m}/\text{s}^2$ (for Isp and propulsion mass calculations)
- **Angle Conversion Factors**:
  - $\text{DEG\_TO\_RAD} = \pi / 180.0 \approx 0.017453292519943295$
  - $\text{RAD\_TO\_DEG} = 180.0 / \pi \approx 57.29577951308232$

### 0.2 Project-Wide Unit Conventions
- **External / API Boundaries**:
  - Distance: kilometers ($\text{km}$)
  - Velocity: kilometers per second ($\text{km}/\text{s}$)
  - Time duration / delay: seconds ($\text{s}$) or minutes ($\text{min}$) where explicitly configured
  - Angles: degrees ($\text{deg}$)
  - Mass: kilograms ($\text{kg}$)
  - Specific impulse: seconds ($\text{s}$)
  - Delta-v budget: meters per second ($\text{m}/\text{s}$)
- **Internal Orbital Calculations**:
  - Angles: radians ($\text{rad}$) for all mathematical and trigonometric formulations
  - Orbital distance: kilometers ($\text{km}$)
  - Orbital velocity: kilometers per second ($\text{km}/\text{s}$)
  - Orbital propagation time step: seconds ($\text{s}$)

### 0.3 Time and UTC Policy
- **UTC Everywhere**: All timestamps across the application and domain layers use UTC.
- **Timezone-Aware**: Only timezone-aware Python datetimes (`timezone.utc`) are permitted in core domain objects and persistence.
- **Strict Naive Rejection**: Naive datetimes are strictly rejected with `ValueError` and never silently assumed to be local time.
- **ISO 8601 Boundaries**: All serialized timestamps at REST API boundaries use ISO 8601 format (e.g. `YYYY-MM-DDTHH:MM:SSZ`).

### 0.4 Planning Defaults
Configured centrally in `app.core.config.Settings`:
- `EPOCH_START_OFFSET_DAYS`: $1 \text{ day}$
- **Altitude Grid**:
  - `ALTITUDE_MIN_KM`: $500 \text{ km}$
  - `ALTITUDE_MAX_KM`: $600 \text{ km}$
  - `ALTITUDE_STEP_KM`: $25 \text{ km}$
  - `REFERENCE_ALTITUDE_KM`: $550 \text{ km}$
- **Inclination Grid**:
  - `INCLINATION_MIN_DEG`: $97.0^\circ$
  - `INCLINATION_MAX_DEG`: $98.0^\circ$
  - `INCLINATION_STEP_DEG`: $0.5^\circ$
  - `REFERENCE_INCLINATION_DEG`: $97.5^\circ$
- **Initial Orbit Angles & Deployment Delay**:
  - `RAAN_DEG`: $0.0^\circ$
  - `U0_DEG` (Initial Argument of Latitude): $0.0^\circ$
  - `DELAY_MIN_MINUTES`: $0 \text{ min}$
  - `DELAY_MAX_MINUTES`: $720 \text{ min}$ ($12 \text{ hours}$)
  - `DELAY_STEP_MINUTES`: $60 \text{ min}$
  - `RAAN_DELAY_COUPLING_DEG_PER_MIN`: $0.25068^\circ/\text{min}$
- **Screening Horizon**:
  - `SCREENING_DAYS`: $3 \text{ days}$
  - `SCREENING_MIN_DAYS`: $1 \text{ day}$
  - `SCREENING_MAX_DAYS`: $7 \text{ days}$
- **Propulsion & Spacecraft**:
  - `DV_BUDGET_M_S`: $100 \text{ m}/\text{s}$
  - `SPACECRAFT_MASS_KG`: $3.0 \text{ kg}$ (3U CubeSat reference)
  - `ISP_SECONDS`: $60 \text{ s}$
- **Multi-Objective Weights**:
  - `FUEL_WEIGHT`: $0.4$
  - `RISK_WEIGHT`: $0.6$ (Sum strictly equals $1.0$)
- **Catalog Source**: `DATA_SOURCE = "celestrak"` (supported: `"celestrak"`, `"spacetrack"`)

### 0.5 Ingestion Etiquette Fetch Intervals
- `CELESTRAK_MIN_FETCH_INTERVAL_HOURS`: $2.0 \text{ hours}$
- `SPACETRACK_MIN_FETCH_INTERVAL_HOURS`: $1.0 \text{ hours}$

### 0.6 Catalog Ingestion & External GP Data Semantics (Phase P4)
- **CelesTrak External GP Data**: Orbital data consumed by D-DATO from CelesTrak originates from General Perturbations (GP) element sets derived from radar and optical tracking. These are mean Keplerian element sets compatible with SGP4 theory.
- **Support for >= 6-Digit Catalog Identifiers**: CelesTrak's GP catalog has expanded beyond legacy 5-digit NORAD identifiers. Newly tracked space objects and debris fragments can have 6-digit catalog numbers (or longer). Because legacy 2-line TLE format cannot represent 6-digit numbers in standard columns, legacy TLE lines are NOT available for those objects. D-DATO must NEVER assume catalog IDs are 5 digits or that every object possesses two raw TLE lines. Both modern OMM formats (JSON/CSV) and legacy TLE are supported through the unified `CanonicalElementRecord`.
- **Mandatory Data Age Display & Storage**: Because low Earth orbit ephemerides degrade rapidly due to atmospheric drag perturbations, the elapsed data age (`data_age_seconds = now_utc - fetched_at`) must always be computed, persisted in `DataSnapshot` and `DebrisObject`, and surfaced in user-facing views.
- **Offline Demo Data Status**: Bundled test fixtures under `demo_data/` are provided strictly for offline development, deterministic verification, and air-gapped testing. Demo data is labeled with `source="demo"` and MUST NOT be presented as current operational tracking data.

---

## 1. Coordinate Frames and State Representations
- **TEME (True Equator, Mean Equinox)**: Native coordinate frame for SGP4 TLE state vectors.
- **GCRS / ECI (Geocentric Celestial Reference System / Earth-Centered Inertial)**: Inertial reference frame used for conjunction screening.
- **Keplerian Elements**:
  - $a$: Semi-major axis ($km$)
  - $e$: Eccentricity (dimensionless)
  - $i$: Inclination ($deg$ or $rad$)
  - $\Omega$: Right Ascension of the Ascending Node (RAAN) ($deg$ or $rad$)
  - $\omega$: Argument of Perigee ($deg$ or $rad$)
  - $\nu$ or $M$: True or Mean Anomaly ($deg$ or $rad$)

## 2. D-DATO Propagation Models (Phase P5)

D-DATO maintains two distinct, intentionally decoupled propagation pathways:

```text
Catalog Debris / Objects                  Candidate Deployment Options
      │                                                │
      ▼                                                ▼
 CanonicalElementRecord                         Candidate Parameters
 (TLE lines or OMM GP)                         (alt, inc, raan, u0, epoch)
      │                                                │
      ▼                                                ▼
  SGP4 Propagator                               CircularJ2Orbit
(SGP4 WGS72/84 Theory)                        (D-DATO Analytic J2 Model)
      │                                                │
      ▼                                                ▼
 TEME StateVector                               TEME StateVector
 (r, v in km, km/s)                            (r, v in km, km/s)
      │                                                │
      └──────────────────────┬─────────────────────────┘
                             ▼
              Future Conjunction Screening
```

### 2.1 SGP4 Propagation (Catalog Debris & Spacecraft)
- **Purpose**: High-fidelity propagation of tracked space debris and active space objects.
- **Inputs**: `CanonicalElementRecord` derived from legacy Two-Line Elements (TLE) or modern Orbit Mean-Elements Messages (OMM).
- **Coordinate Frame**: True Equator, Mean Equinox (TEME) Cartesian frame.
- **Output Units**: Position in kilometers ($\text{km}$), velocity in kilometers per second ($\text{km}/\text{s}$).
- **UTC Time Handling**: Requires explicit timezone-aware UTC Python datetimes (`timezone.utc`). Times are converted to Julian Date whole and fractional parts via SGP4 `jday(year, mon, day, hr, min, sec)` with sub-second microsecond precision. Naive datetimes are strictly rejected.
- **SGP4 Error Code Translation**: Non-zero SGP4 exit codes are translated into domain `PropagationError` exceptions containing object ID, timestamp, error code, and descriptive diagnostic messages (e.g. decayed orbit, unphysical mean motion or eccentricity).
- **6-Digit Catalog ID Handling**: SGP4's internal Alpha-5 encoding restricts numerical satellite numbers to $\le 339999$. When canonical catalog IDs exceed this boundary (e.g. `700001`), the propagator employs a deterministic numerical surrogate (0) strictly for internal numerical evaluation. The canonical ID remains unmutated across the application, database, and generated `StateVector.object_id`.

### 2.2 Circular J2 Secular Model (Analytical Candidate Screening)
- **Purpose**: Rapid analytical candidate orbit generation and screening across multi-day deployment windows without relying on artificial TLE generation.
- **Circular Assumption**: Candidate orbits are assumed circular ($e = 0$, $p = a = R_E + \text{altitude}_{\text{km}}$).
- **Secular Perturbation Equations**:
  $$\dot{\Omega} = -\frac{3}{2} J_2 n \left(\frac{R_E}{a}\right)^2 \cos(i)$$
  $$\dot{\omega} = \frac{3}{4} J_2 n \left(\frac{R_E}{a}\right)^2 \left(5\cos^2(i) - 1\right)$$
  $$\dot{u} = n + \dot{\omega}$$
  where $n = \sqrt{\mu / a^3}$ (rad/s) and $u$ is the argument of latitude.
- **Analytical Position**: Evaluated via classical 3-1 rotation sequence $R_3(\Omega(t)) R_1(i)$ on perifocal vector $[a\cos u, a\sin u, 0]^T$ to yield TEME Cartesian coordinates $[x, y, z]^T$.
- **Analytical Velocity**: Formulated exactly as the analytical time-derivative $\mathbf{v}(t) = \frac{d\mathbf{r}}{dt}$:
  $$\mathbf{v}(t) = R_3(\Omega(t)) R_1(i) \begin{bmatrix} -a \dot{u} \sin u \\ a \dot{u} \cos u \\ 0 \end{bmatrix} + \dot{\Omega} (\hat{\mathbf{k}} \times \mathbf{r}(t))$$
  accounting for both in-plane orbital motion and nodal precession rate.
- **Screening Scope**: This is an analytical screening model designed for coarse evaluation of candidate deployment orbits. It is NOT intended to replace numerical orbit determination or operational SGP4 TLE generation.

### 2.3 Critical Distinction: SGP4 Gravity Convention vs. D-DATO Constants
- **SGP4 Gravity Standards**: The SGP4 propagator operates under WGS-72 or WGS-84 gravitational constants embedded in the official SGP4 library (`gravconst=WGS72`). D-DATO's `MU`, `RE`, and `J2` constants must NEVER be silently injected into SGP4 internals.
- **D-DATO Constants**: Project constants (`MU = 398600.4418 km^3/s^2`, `RE = 6378.137 km`, `J2 = 1.08262668e-3`) govern the analytical candidate model, Keplerian conversions, delta-v formulas, and multi-objective ranking exclusively.

### 2.4 D-DATO Candidate Generation (Phase P6)
- **Cartesian Product Dimensions**:
  Candidates are generated from the Cartesian product of exactly 3 discrete search dimensions:
  $$\text{Altitude Grid} \times \text{Inclination Grid} \times \text{Deployment Delay Grid}$$
  RAAN is **NOT** an independent Cartesian-product dimension. RAAN is derived from deployment delay using the configured coupling.
- **Inclusive Grid Endpoints & Numerical Stability**:
  Grid endpoints are inclusive when the step size lands on the upper bound. Decimal arithmetic is used to evaluate step intervals, preventing binary floating-point accumulation drift (such as `97.4999999997`). If a step exceeds the maximum without landing on it, the endpoint is omitted rather than artificially forced.
- **Authoritative Planning Defaults**:
  - Altitude: $500 \text{ km}$ to $600 \text{ km}$, step $25 \text{ km} \rightarrow [500, 525, 550, 575, 600]$ (5 values)
  - Inclination: $97.0^\circ$ to $98.0^\circ$, step $0.5^\circ \rightarrow [97.0, 97.5, 98.0]$ (3 values)
  - Deployment Delay: $0 \text{ min}$ to $720 \text{ min}$, step $60 \text{ min} \rightarrow [0, 60, 120, \dots, 720]$ (13 values)
  - **Default Candidate Population**:
    $$5 \times 3 \times 13 = 195 \text{ candidates}$$
- **Strict Maximum Candidate Limit (MAX_CANDIDATES = 300)**:
  D-DATO enforces an upper ceiling of 300 candidates (`MAX_CANDIDATES = 300`). If a user's requested grid parameters yield $> 300$ candidates, the system raises a clear `CandidateGenerationError` reporting the calculated count, maximum allowed, and dimension breakdown. It **never** silently truncates, randomly samples, or drops candidates.
- **Deterministic Ordering**:
  Candidates are generated in a strict, deterministic sequence:
  1. Ascending altitude
  2. Ascending inclination
  3. Ascending deployment delay
- **Deterministic Candidate Identifiers**:
  Every candidate is assigned a unique, reproducible, human-readable ID formatted as:
  `ALT{altitude}_INC{inclination}_DELAY{delay}` (e.g. `ALT500_INC97.0_DELAY000` through `ALT600_INC98.0_DELAY720`), allowing unambiguous parameter identification and auditability.
- **RAAN-Delay Coupling**:
  Derived using the fixed planning parameter `RAAN_DELAY_COUPLING_DEG_PER_MIN = 0.25068 deg/min`:
  $$\Omega_{\text{derived}} = (\Omega_{\text{base}} + 0.25068 \times \text{delay}_{\text{minutes}}) \pmod{360^\circ}$$
  The result is normalized into $[0.0, 360.0)^\circ$.
  The system explicitly maintains both `base_raan_deg` (the original plan reference) and `raan_deg` / `predicted_raan_deg` (the coupled candidate value).
- **Deployment Epoch**:
  $$\text{deployment\_epoch} = \text{epoch\_start} + \text{timedelta}(\text{minutes}=\text{delay})$$
  Both `epoch_start` and `deployment_epoch` are strictly timezone-aware UTC datetimes.
- **Scope Boundary**:
  Candidate generation is a pure in-memory astrodynamic planning stage. It has no dependencies on database sessions, HTTP requests, SGP4 propagation, delta-v calculations, fuel mass, conjunction screening, or ranking.

## 3. D-DATO Delta-v and Propellant Estimation (Phase P7)

> **Important Distinction**:
> "This is an early-stage conservative screening estimate, not an operational maneuver plan."
> It is not a flight-certified delta-v budget, a high-fidelity finite-burn simulation, or a true mission trajectory optimizer.

### 3.1 Reference Orbit & Geometry
- **Reference Orbit**: Defined by `REFERENCE_ALTITUDE_KM = 550.0 km` and `REFERENCE_INCLINATION_DEG = 97.5 deg`.
- **Circular Orbital Radii**:
  $$r_{\text{ref}} = R_E + \text{altitude}_{\text{ref}} = 6378.137 + 550.0 = 6928.137 \text{ km}$$
  $$r_{\text{cand}} = R_E + \text{altitude}_{\text{cand}}$$
  Validates $r > R_E$ and $\text{altitude} > 0$.
- **Circular Orbital Velocity**:
  $$v_{\text{circular}} = \sqrt{\frac{\mu}{r}} \quad (\text{km/s})$$
  For the default reference orbit, $v_{\text{ref}} \approx 7.58444 \text{ km/s}$. Internal orbital velocities remain strictly in $\text{km/s}$.

### 3.2 Hohmann Altitude-Transfer Delta-V
For reference radius $r_1$ and candidate radius $r_2$:
- If $r_1 = r_2$: $\Delta v_{\text{transfer}} = 0.0 \text{ km/s}$ (no maneuvers calculated for zero altitude difference).
- If $r_1 \ne r_2$:
  $$\Delta v_1 = \sqrt{\frac{\mu}{r_1}} \left( \sqrt{\frac{2r_2}{r_1 + r_2}} - 1 \right)$$
  $$\Delta v_2 = \sqrt{\frac{\mu}{r_2}} \left( 1 - \sqrt{\frac{2r_1}{r_1 + r_2}} \right)$$
  $$\Delta v_{\text{transfer}} = |\Delta v_1| + |\Delta v_2| \quad (\text{km/s})$$

### 3.3 Circular Plane-Change Delta-V
For an inclination difference $\Delta i = |\text{inclination}_{\text{cand}} - \text{inclination}_{\text{ref}}|$:
- If $\Delta i = 0$: $\Delta v_{\text{plane}} = 0.0 \text{ km/s}$.
- If $\Delta i > 0$: Simple circular plane change at reference speed:
  $$\Delta v_{\text{plane}} = 2 v_{\text{ref}} \sin\left(\frac{\Delta i}{2}\right) \quad (\text{km/s})$$
  This is intentionally a conservative screening estimate and does not optimize maneuver placement along the Hohmann transfer.

### 3.4 Conservative Total Delta-V
> "The P7 total delta-v is the scalar sum of altitude-transfer and plane-change estimates; burns are not vector-combined or optimized."
$$\Delta v_{\text{total, km/s}} = \Delta v_{\text{transfer, km/s}} + \Delta v_{\text{plane, km/s}}$$
Converted to $\text{m/s}$ at the domain boundary:
$$\Delta v_{\text{total, m/s}} = \Delta v_{\text{total, km/s}} \times 1000.0$$
$$\Delta v_{\text{transfer, m/s}} = \Delta v_{\text{transfer, km/s}} \times 1000.0$$
$$\Delta v_{\text{plane, m/s}} = \Delta v_{\text{plane, km/s}} \times 1000.0$$

### 3.5 Tsiolkovsky Rocket Equation & Propellant Mass
Evaluated from standard ideal rocket equation:
$$\Delta v = I_{\text{sp}} g_0 \ln\left(\frac{m_0}{m_f}\right) \implies m_f = m_0 \exp\left(-\frac{\Delta v}{I_{\text{sp}} g_0}\right)$$
$$m_p = m_0 - m_f = m_0 \left(1 - \exp\left(-\frac{\Delta v}{I_{\text{sp}} g_0}\right)\right)$$
- **Mass Semantics**: `SPACECRAFT_MASS_KG` (default $3.0 \text{ kg}$) is interpreted as the initial/wet mass ($m_0$) for this screening estimator. It does not model dry mass breakdowns, tankage, pressurant, residuals, or throttling losses.
- **Specific Impulse ($I_{\text{sp}}$)**: `ISP_SECONDS` (default $60.0 \text{ s}$).
- **Standard Gravity ($g_0$)**: $9.80665 \text{ m/s}^2$.
- **Numerical Stability**: Computed using $-m_0 \times \text{expm1}(-\Delta v / (I_{\text{sp}} g_0))$ to prevent catastrophic cancellation at small $\Delta v$.
- **Fuel Fraction**:
  $$\text{fuel\_fraction} = \frac{m_p}{m_0}$$
- **Zero-Maneuver Identity**: For $\Delta v = 0.0$, propellant $m_p = 0.0$, fuel fraction $= 0.0$, and $m_f = m_0$.

### 3.6 Delta-V Budget Evaluation
Evaluated against `DV_BUDGET_M_S` (default $100.0 \text{ m/s}$):
$$\text{within\_dv\_budget} = (\Delta v_{\text{total, m/s}} \le \text{dv\_budget\_m/s})$$
A candidate at exactly the budget is considered within budget.

### 3.7 Units Summary
- Orbital distances / radii: kilometers ($\text{km}$)
- Orbital velocities / intermediate delta-vs: kilometers per second ($\text{km/s}$)
- Final delta-v values: meters per second ($\text{m/s}$)
- Mass values: kilograms ($\text{kg}$)
- Specific impulse: seconds ($\text{s}$)

## 4. D-DATO Conjunction Screening (Phase P8)

> **IMPORTANT DISCLAIMER**:
> **This is a screening method, not a true collision-probability calculation.**
> **Conjunction-event miss distance is not collision probability.**
> Phase P8 produces physical close-approach encounter records based purely on orbital trajectories and distance thresholds.

### 4.1 Propagation Models & Common Reference Frame
- **Candidate Orbit Model**: Circular J2 secular model anchored strictly at `candidate.deployment_epoch` with derived `candidate.raan_deg` and `candidate.u0_deg`. It does **not** double-count deployment delay or re-propagate from `epoch_start`.
- **Debris Orbit Model**: SGP4 initialized from canonical elements (`CanonicalElementRecord`).
- **Common Reference Frame**: True Equator, Mean Equinox (TEME) Cartesian coordinates $[x, y, z]$ in kilometers, $[v_x, v_y, v_z]$ in $\text{km/s}$. States are strictly compared at common UTC timestamps.

### 4.2 Screening Population & Conservative Prefiltering
- **Screening Population**: Includes catalog objects classified as `debris`, `rocket_body`, or `unknown`. Objects explicitly classified as `payload` are excluded. `unknown` objects are retained conservatively.
- **Altitude Envelope Prefilter**:
  If perigee altitude $h_p$ and apogee altitude $h_a$ are computable:
  Objects are rejected only if candidate altitude is outside $[h_p - \Delta h_{\text{margin}}, h_a + \Delta h_{\text{margin}}]$, where $\Delta h_{\text{margin}} = 300.0 \text{ km}$.
  If metadata is unavailable, the object is retained conservatively.
- **No Inclination Rejection**: Inclination is **never** used to reject objects because orbits with different inclinations regularly intersect spatially.

### 4.3 Time Chunking & Two-Pass Screening Architecture
To prevent unbounded memory allocation across $3 \text{ days} \times N_{\text{debris}}$ state arrays, screening executes in configurable time chunks (`SCREENING_TIME_CHUNK_SECONDS = 3600 \text{ s}`):

#### Pass 1: Coarse Screening
- **Time Step**: $\Delta t_{\text{coarse}} = 30 \text{ seconds}$ (`SCREENING_COARSE_STEP_SECONDS`).
- **Coarse Detection Threshold**: $d_{\text{coarse}} = 260.0 \text{ km}$ (`SCREENING_COARSE_THRESHOLD_KM`).
- **Rationale for 260 km**: For high relative speeds (up to $15 \text{ km/s}$), a close approach chord across a 260 km radius sphere takes $\approx 34.5 \text{ s}$ to traverse. Sampling at 30-second steps guarantees at least one sample falls within 260 km for any approach passing within 25 km.
- **Local Minimum Detection**: A coarse sample at $t_i$ is flagged as an approach bracket if:
  $$d(t_i) \le d(t_{i-1}) \quad \text{and} \quad d(t_i) \le d(t_{i+1}) \quad \text{and} \quad d(t_i) \le 260.0 \text{ km}$$
  or if adjacent samples straddle the 260 km threshold.
- **Bracket Formation**: Interval $[t_i - \Delta t_{\text{coarse}}, t_i + \Delta t_{\text{coarse}}]$ clamped to $[t_{\text{start}}, t_{\text{end}}]$.

#### Pass 2: Numerical TCA Refinement
- **Optimization Method**: Bounded 1-D scalar numerical minimization via `scipy.optimize.minimize_scalar(method="bounded")`.
- **Independent Variable**: Elapsed seconds since bracket start, avoiding datetime overhead inside the objective loop.
- **Objective Function**:
  $$d(t) = \|\mathbf{r}_{\text{candidate}}(t) - \mathbf{r}_{\text{debris}}(t)\|$$
- **Convergence Parameters**: Tolerance $\text{xtol} = 0.01 \text{ s}$ (`SCREENING_TCA_XTOL_SECONDS`), max iterations $= 100$.
- **Validation**: Independent post-minimization re-evaluation of exact states at the derived TCA, clamping to bracket boundaries, and endpoint fallback on optimizer failure.
- **Event Acceptance Threshold**: An event is retained **only** if:
  $$d_{\text{refined}}(t_{\text{TCA}}) \le 25.0 \text{ km} \quad (\text{SCREENING\_EVENT\_THRESHOLD\_KM})$$

### 4.4 Relative Velocity Magnitude
At the refined TCA timestamp $t_{\text{TCA}}$:
$$\mathbf{v}_{\text{rel}} = \mathbf{v}_{\text{candidate}}(t_{\text{TCA}}) - \mathbf{v}_{\text{debris}}(t_{\text{TCA}})$$
$$v_{\text{rel}} = \|\mathbf{v}_{\text{rel}}\| \quad (\text{km/s})$$
Recorded directly as `relative_velocity_km_s`.

### 4.5 Deterministic Deduplication & Event Ordering
- **Pair Grouping**: Grouped by $(\text{candidate\_id}, \text{debris\_key})$.
- **Merge Window**: Encounters for the same pair within $30.0 \text{ seconds}$ are merged, retaining the single event with the minimum refined miss distance. Genuinely separated encounters ($> 30 \text{ s}$) are preserved.
- **Deterministic Sort Order**:
  1. `candidate_id`
  2. `tca` (UTC)
  3. `miss_distance_km`
  4. `debris_norad_id`

### 4.6 Safety Cap & Error Isolation
- **Safety Cap**: Capped at SCREENING_MAX_EVENTS_PER_CANDIDATE = 1000 to prevent memory exhaustion on dense catalogs.
- **Error Isolation**: Failure in SGP4 propagation for a single debris object records a diagnostic warning, skips that object, and continues screening remaining objects. Candidate failures raise ScreeningError.

## 5. D-DATO Screening Risk Score (Phase P9)

> **IMPORTANT POSITIONING & DISCLAIMER**:
> **D-DATO risk is a bounded [0, 100] early-stage screening index.**
> **It is NOT probability of collision ($P_c$).**
> **It is NOT probability of impact.**
> **It is NOT an operational flight-safety determination.**
> **Loaded terminology (such as "safe", "dangerous", or "guaranteed collision") is strictly forbidden.**
> The score provides transparent, explainable comparison among candidate deployment windows based on close-approach screening events.

### 5.1 Specification Status & Fallback Heuristic
The original D-DATO specification dictates multi-attribute evaluation for candidate mission envelopes but does not specify an exact closed-form risk formula. Therefore:
**No exact formula found; documented fallback heuristic implemented.**

The implemented model is designated:
`fallback_heuristic_v1: Fallback heuristic for early-stage screening.`

### 5.2 Mathematical Formulation

For a candidate orbit with zero accepted conjunction events:
$$\text{risk\_score} = 0.0$$

For a candidate orbit with one or more accepted P8 conjunction events:
Let:
- $d_{\min} = \min_{i} (\text{miss\_distance}_i) \quad (\text{km})$: minimum refined miss distance among accepted events.
- $N$: count of distinct accepted conjunction events ($N \ge 1$).
- $D_{\text{EVENT}} = 25.0 \text{ km}$ (`SCREENING_EVENT_THRESHOLD_KM`): P8 conjunction event acceptance threshold.
- $N_{\text{sat}} = 5$ (`RISK_EVENT_SATURATION_COUNT`): encounter-count saturation threshold.
- $w_{\text{prox}} = 0.8$ (`RISK_PROXIMITY_WEIGHT`): proximity component weight.
- $w_{\text{cnt}} = 0.2$ (`RISK_EVENT_COUNT_WEIGHT`): encounter-count component weight ($w_{\text{prox}} + w_{\text{cnt}} = 1.0$).

#### Proximity Component Score
$$\text{proximity\_score} = \text{clamp}\left(100.0 \times \left(1.0 - \frac{d_{\min}}{D_{\text{EVENT}}}\right), 0.0, 100.0\right)$$
- At $d_{\min} = 25.0 \text{ km}$: $\text{proximity\_score} = 0.0$
- At $d_{\min} = 12.5 \text{ km}$: $\text{proximity\_score} = 50.0$
- At $d_{\min} = 0.0 \text{ km}$: $\text{proximity\_score} = 100.0$

#### Encounter-Count Component Score
$$\text{count\_score} = \min\left(100.0 \times \frac{N}{N_{\text{sat}}}, 100.0\right)$$
- $N = 1 \implies 20.0$
- $N = 2 \implies 40.0$
- $N = 3 \implies 60.0$
- $N = 4 \implies 80.0$
- $N \ge 5 \implies 100.0$

#### Composite Scalar Risk Score
$$\text{risk\_score} = \text{clamp}\left(w_{\text{prox}} \cdot \text{proximity\_score} + w_{\text{cnt}} \cdot \text{count\_score}, 0.0, 100.0\right)$$

### 5.3 Formal Score Properties
1. **Bounded**: $0.0 \le \text{risk\_score} \le 100.0$ strictly for all inputs.
2. **Zero-Event Baseline**: If $N = 0$, $\text{risk\_score} = 0.0$, $\text{proximity\_score} = 0.0$, $\text{count\_score} = 0.0$, and distance/velocity metrics are `None`.
3. **Monotonic with Miss Distance**: For any fixed event count $N$, a smaller $d_{\min}$ strictly never decreases the risk score ($\partial \text{risk} / \partial d_{\min} \le 0$).
4. **Monotonic with Event Count**: For any fixed minimum miss distance $d_{\min}$, a larger accepted event count $N$ strictly never decreases the risk score ($\partial \text{risk} / \partial N \ge 0$).
5. **Exact Event Threshold**: An event at exactly $d_{\min} = 25.0 \text{ km}$ yields a proximity component of exactly $0.0$.
6. **Zero-Distance Event**: An event at $d_{\min} = 0.0 \text{ km}$ yields a proximity component of exactly $100.0$.
7. **Saturation Invariance**: Beyond $N_{\text{sat}} = 5$, the encounter-count component remains bounded at $100.0$.
8. **Determinism**: Given identical events, the output is bitwise identical with zero stochasticity.

### 5.4 Accepted Event Definition & Multi-Event Handling
- **Accepted Conjunction Event**: Only events meeting the P8 refined threshold ($d \le 25.0 \text{ km}$) are valid inputs. Events with $d > 25.0 \text{ km}$ are strictly rejected with a domain error (`RiskScoringError`).
- **Aggregation**:
- Minimum miss distance: $d_{\min} = \min_{i} (d_i)$
- Minimum relative velocity: $v_{\min} = \min_{i} (v_{\text{rel}, i})$
- Maximum relative velocity: $v_{\max} = \max_{i} (v_{\text{rel}, i})$
- Accepted count: $N = \text{len}(\text{events})$
- **Deduplication**: Relies on P8's $30\text{-second}$ temporal deduplication window per candidate-debris pair.

### 5.5 Relative Velocity Treatment
- Relative velocity magnitude $v_{\text{rel}}$ (in $\text{km/s}$) is an essential physical metric representing encounter energetics.
- However, relative velocity is **NOT** scaled into the scalar risk score.
- Arbitrarily normalizing velocity (e.g. asserting $15\text{ km/s} = 100$ risk) would inject undocumented, uncalibrated scaling and falsely mimic physical collision probability.
- Relative velocity is preserved and reported transparently in `minimum_relative_velocity_km_s` and `maximum_relative_velocity_km_s`.

### 5.6 Data Freshness & Ephemeris Uncertainty Semantics
- TLE/OMM ephemerides degrade over time due to unmodeled upper atmospheric density variations and solar flux dynamics.
- Rather than creating misleading statistical confidence intervals (e.g. "85% confidence"), D-DATO categorizes data freshness into transparent tiers:
- **`nominal`**: Catalog data age $\le 3 \text{ days}$ ($259,200 \text{ s}$, `RISK_DATA_AGE_ELEVATED_SECONDS`).
- **`elevated`**: Catalog data age $> 3 \text{ days}$. Ephemeris uncertainty is elevated due to atmospheric drag perturbations.
- **`unknown`**: Catalog data age is unavailable. Ephemeris uncertainty is unquantified.

### 5.7 Explainable Component Breakdown
Every assessment returns an immutable `RiskAssessment` containing:
- `risk_score`: composite scalar $[0, 100]$
- `proximity_score`: distance contribution $[0, 100]$
- `event_count_score`: frequency contribution $[0, 100]$
- `accepted_event_count`: integer count of events $\le 25\text{ km}$
- `minimum_miss_distance_km`: closest approach distance
- `minimum_relative_velocity_km_s` / `maximum_relative_velocity_km_s`: relative velocity envelope
- `data_age_seconds`: catalog age in seconds
- `uncertainty_level`: `"nominal"`, `"elevated"`, or `"unknown"`
- `uncertainty_notes`: human-readable explanation
- `scoring_method`: identifier (`"fallback_heuristic_v1"`)

## 6. D-DATO Candidate Ranking (Phase P10)

> **IMPORTANT POSITIONING & SEMANTICS**:
> - D-DATO ranking is an early-stage multi-objective screening heuristic.
> - It does **NOT** declare an "optimal orbit", "safest orbit", or "guaranteed collision-free" path.
> - Candidates are designated **"screening-ranked candidates"**.
> - P10 is a pure deterministic post-processing step consuming precomputed P7 delta-v metrics and P9 risk screening scores.
> - P10 **NEVER** calls orbit propagation, SGP4, conjunction screening, TCA numerical refinement, or external network services.

### 6.1 Authoritative Specification Status
The original D-DATO specification (`SPEC.md` Stage 6) outlines multi-objective candidate evaluation balancing fuel consumption and conjunction risk, but specifies no exact closed-form scalar ranking formula or normalization denominator.
Therefore:
**No exact formula found; documented fallback heuristic implemented (`fallback_ranking_v1`).**

### 6.2 Ranking Inputs
The ranking engine consumes three immutable inputs per candidate:
1. **Candidate Geometry (P6)**: `CandidateOrbit` (or `Candidate` ORM / dict) containing `altitude_km`, `inclination_deg`, `raan_deg`, `deployment_delay_minutes`, `deployment_epoch`.
2. **Delta-V & Propulsion Estimate (P7)**: `DeltaVEstimate` providing `delta_v_m_s` (total maneuver delta-v), `propellant_mass_kg`, `fuel_fraction`, and `within_dv_budget`.
3. **Screening Risk Assessment (P9)**: `RiskAssessment` providing bounded `risk_score` in $[0, 100]$, `accepted_event_count`, `minimum_miss_distance_km`, and `uncertainty_level`.

### 6.3 Metric Normalization

#### 6.3.1 Fuel Cost Normalization (Min-Max)
Delta-v is normalized dynamically across the evaluated candidate population:
$$dv_{\min} = \min_{j} (\Delta v_j), \quad dv_{\max} = \max_{j} (\Delta v_j)$$

For candidate $i$:
$$\text{normalized\_fuel\_cost}_i = \begin{cases} 100.0 \times \frac{\Delta v_i - dv_{\min}}{dv_{\max} - dv_{\min}} & \text{if } dv_{\max} > dv_{\min} \\ 0.0 & \text{if } dv_{\max} = dv_{\min} \text{ or } N = 1 \end{cases}$$
- Minimum delta-v candidate receives a fuel cost of $0.0$.
- Maximum delta-v candidate receives a fuel cost of $100.0$.
- If all candidates require identical delta-v (or for a single candidate), all receive $0.0$, because fuel consumption cannot differentiate the options.
- The delta-v budget is a feasibility criterion; it is **NOT** used as an arbitrary normalization denominator.

#### 6.3.2 Risk Cost Normalization
Phase P9 screening risk is already strictly bounded in $[0, 100]$:
$$\text{normalized\_risk\_cost}_i = \text{risk\_score}_i$$
Risk is **NOT** rescaled using min-max across the population. This preserves the absolute physical meaning of the P9 close-approach screening scale.

### 6.4 Weights & Composite Desirability Score
Evaluated using centralized configuration:
- `FUEL_WEIGHT = 0.4` (`settings.FUEL_WEIGHT`)
- `RISK_WEIGHT = 0.6` (`settings.RISK_WEIGHT`)
- Constraint: $w_{\text{fuel}} \ge 0, \quad w_{\text{risk}} \ge 0, \quad w_{\text{fuel}} + w_{\text{risk}} = 1.0$

Because both components represent "costs" where lower is better:
$$\text{composite\_cost}_i = w_{\text{fuel}} \cdot \text{normalized\_fuel\_cost}_i + w_{\text{risk}} \cdot \text{normalized\_risk\_cost}_i$$

Converted to a higher-is-better desirability metric:
$$\text{composite\_score}_i = \text{clamp}(100.0 - \text{composite\_cost}_i, 0.0, 100.0)$$
- Best possible composite score = $100.0$ (zero fuel penalty, zero conjunction risk).
- Worst possible composite score = $0.0$ (maximum fuel penalty, maximum conjunction risk).
- Terminology: Referred to as `composite_screening_score` or `ranking_score`.

### 6.5 Feasibility & Delta-V Budget Semantics
Candidates exceeding the delta-v budget (`within_dv_budget = False`) are **NOT** discarded or filtered out of the ranking.
- All valid candidates are ranked transparently.
- The `within_dv_budget` boolean flag is preserved on each `RankedCandidate`.
- Downstream orchestration or user interfaces can filter or highlight out-of-budget options as desired.

### 6.6 Deterministic Tie-Breaking & Contiguous Ranks
Ranking is strictly deterministic and ordered by:
1. `composite_score` **descending** (higher desirability first)
2. `risk_score` **ascending** (lower screening risk preferred)
3. `delta_v_m_s` **ascending** (lower fuel consumption preferred)
4. `candidate_id` **ascending** (lexicographical string tie-breaker)

After sorting, contiguous integer ranks are assigned:
$$\text{rank} \in \{1, 2, 3, \dots, N\}$$

### 6.7 Zero Re-Screening Guarantee
The ranking engine consumes precomputed results. Calling any orbital propagation, fuel evaluation, or conjunction screening method inside `rank_candidates` is strictly prohibited.

---

## 7. D-DATO End-to-End Planning Pipeline (Phase P11)

### 7.1 Objective and Scope
Phase P11 provides the synchronous orchestration layer (`PipelineService`) connecting the tested astrodynamic and scoring components into an end-to-end mission planning pipeline:
1. **Catalog Ingestion (P4)**: Ingests external space debris catalogs or bundled demo elements via `IngestionService`.
2. **Candidate Generation (P6)**: Generates the Cartesian product candidate orbit grid (bounded to $\le 300$ candidates; default 195).
3. **Delta-V & Fuel Evaluation (P7)**: Evaluates conservative Hohmann transfer and plane-change fuel requirements for each candidate.
4. **Conjunction Screening & TCA Refinement (P8)**: Propagates candidate orbits with Circular $J_2$, debris orbits with SGP4, performs 30-second coarse screening, and numerically refines TCA for close approaches $\le 25\text{ km}$.
5. **Physical Risk Assessment (P9)**: Evaluates bounded $0\text{--}100$ screening risk scores from accepted conjunction events.
6. **Multi-Objective Candidate Ranking (P10)**: Ranks candidates using normalized fuel costs ($40\%$) and screening risk ($60\%$).
7. **Atomic Result Persistence (P3)**: Bulk persists evaluated candidates, conjunction events, and updates run status.
8. **Domain Result Delivery**: Returns an immutable `PipelineResult` domain object decoupled from database sessions and web frameworks.

### 7.2 Stage Sequence & Progress Allocation
Progress is tracked deterministically across coarse stage boundaries:
- `ingestion`: $0\% \rightarrow 15\%$
- `candidate_generation`: $15\% \rightarrow 25\%$
- `fuel_estimation`: $25\% \rightarrow 35\%$
- `conjunction_screening`: $35\% \rightarrow 75\%$
- `risk_assessment`: $75\% \rightarrow 85\%$
- `ranking`: $85\% \rightarrow 95\%$
- `persistence`: $95\% \rightarrow 99\%$
- `completed`: $100\%$

### 7.3 Run Lifecycle Semantics
- **Execution Start**:
  - `Run.status = "running"`
  - `Run.started_at = now_utc()`
  - `Run.progress_percent = 0.0`
- **Successful Completion**:
  - `Run.status = "completed"`
  - `Run.progress_percent = 100.0`
  - `Run.current_stage = "completed"`
  - `Run.completed_at = now_utc()`
  - `Run.error_message = None`
- **Stage Failure**:
  - `Run.status = "failed"`
  - `Run.current_stage = "failed"`
  - `Run.completed_at = now_utc()`
  - `Run.error_message` records descriptive diagnostic information without leaking secrets.

### 7.4 Provenance & Run Isolation
- Every pipeline execution is bound to a distinct `run_id`.
- Repeated runs of the same `Plan` generate independent sets of candidates and conjunction events.
- Historical run provenance is strictly preserved; prior runs are never overwritten or deleted automatically.

### 7.5 Computational Efficiency & Zero Duplicate Work
- **Fuel Evaluation**: Executed exactly once per candidate ($N$ times total).
- **Conjunction Screening**: Executed exactly once per candidate against the canonical debris catalog.
- **Risk Assessment**: Evaluated once per candidate using the candidate's accepted conjunction events. Candidates with 0 conjunction events receive `risk_score = 0.0`.
- **Ranking**: Evaluated once across the candidate set. Does not trigger re-screening or recalculations.

### 7.6 Demo Mode & Air-Gapped Execution
- When `plan.demo_mode = True`, the ingestion stage utilizes local bundled fixtures (`demo_data/`) without making any network socket calls.
- Air-gapped socket testing verifies complete execution without external network connectivity.

---

## 8. D-DATO Async Execution (Phase P12)

### 8.1 Architectural Role & Synchronous Boundary
- **Synchronous Core**: Phase P11 remains the pure synchronous scientific computation engine (`PipelineService.run_pipeline`).
- **Asynchronous Orchestration**: Phase P12 introduces `RunService` and `WorkerManager` to provide non-blocking execution, thread management, and lifecycle state observation.
- **REST Boundary**: Phase P13 will expose these service methods via FastAPI endpoints (`POST /plans`, `GET /runs/{id}`, `GET /runs/{id}/results`).

### 8.2 Lifecycle States & Transition Grammar
Run status transitions are strictly governed:
- `queued`: Initial state upon creation; remains queued while waiting in the worker executor queue.
- `running`: Transited when the background worker thread begins execution.
- `completed`: Terminal state upon successful pipeline completion, full result persistence, and 100% progress.
- `failed`: Terminal state if worker submission, execution, or pipeline stages fail. Preserves diagnostics in `Run.error_message`.
- `cancelled`: Reserved for future runtime cancellation.

Terminal states (`completed`, `failed`, `cancelled`) cannot transition to any other state. Attempting to resubmit or restart a completed or failed run raises `RunLifecycleError`.

### 8.3 Worker Concurrency & Serialization
- Concurrency defaults to `WORKER_MAX_CONCURRENCY = 1` (`settings.WORKER_MAX_CONCURRENCY`).
- SGP4 propagation and numerical TCA refinement are CPU-heavy operations. Running screening runs serially prevents CPU core thrashing and avoids concurrent SQLite single-writer lock contention.
- When multiple runs are submitted, subsequent runs remain in the database `queued` state until the worker thread picks them up.

### 8.4 Process-Local Futures vs. Database State of Truth
- In-process `concurrent.futures.Future` objects are tracked in `WorkerManager._futures` solely for process-local execution callbacks and active tracking.
- The PostgreSQL/SQLite database `Run.status` is the single authoritative source of truth.
- *Limitation*: In-process execution is not a durable distributed queue (such as Celery or RabbitMQ). If the backend process terminates unexpectedly, active futures are lost; database records reflect their last committed status.





