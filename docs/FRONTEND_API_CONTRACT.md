# D-DATO Frontend API Contract & Integration Guide

**Version**: 1.0 (Phase P18 Contract Freeze)  
**Audience**: Person 2 (Frontend Developer / React & Visualization Engineer)  
**System**: D-DATO (Debris-Aware Orbit & Deployment-Window Planner)  
**Base URL**: `/api/v1`

---

## 1. Non-Operational Scope & System Principles

> [!IMPORTANT]
> **NON-OPERATIONAL POSITIONING**  
> D-DATO is an early-stage mission planning and screening aid. It is **NOT** a certified collision-probability system, operational conjunction assessment tool, maneuver planner, CDM generator, or launch COLA clearing system. All terminology in UI displays must reflect screening terminology (*"ranked screening candidate"*, *"close-approach event"*, *"reference comparison"*).

### Core Architectural Principles for the Frontend:
1. **Frontend is Strictly a Presentation & Interaction Layer**:
   - The frontend consumes persisted backend results.
   - The frontend **MUST NEVER** implement orbital propagation, Keplerian mechanics, SGP4 models, or numerical time-stepping.
   - The frontend **MUST NEVER** recalculate delta-v, propellant mass, fuel fractions, risk scores, or candidate rankings.
2. **System of Record**:
   - All candidate options, conjunction events, risk grids, trajectories, and validation reports are computed and persisted by the backend before presentation.
3. **Execution Lifecycle Pattern**:
   - Mission planning is asynchronous: `POST /api/v1/plans` returns `202 Accepted` with a `run_id`.
   - The frontend polls `GET /api/v1/runs/{run_id}` until reaching terminal state (`completed` or `failed`).
   - All subsequent result endpoints are read-only and return instantly.

---

## 2. Standard Physical Units & Conventions

| Quantity | API Standard Unit | Notes / Formatting |
|---|---|---|
| **Angles** | Degrees (`°`) | `altitude_km`, `inclination_deg`, `raan_deg`, `u0_deg` |
| **Altitude / Distances** | Kilometers (`km`) | Orbit altitude, miss distance, screening threshold |
| **Delta-V** | Meters / second (`m/s`) | Total impulse budget & required maneuver costs |
| **Mass** | Kilograms (`kg`) | Spacecraft dry mass & required propellant mass |
| **Velocities** | Kilometers / second (`km/s`) | Relative encounter velocity at close approach |
| **Durations / Offsets** | Minutes (`min`) or Days | Deployment delay is in minutes; screening period in days |
| **Timestamps** | UTC ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) | Always timezone-aware UTC strings ending in `Z` |
| **Globe Coordinates** | True Equator, Mean Equinox (**TEME**) | Cartesian coordinates in kilometers: `x_km`, `y_km`, `z_km` |
| **Heatmap Metric** | Risk Score (`0.0` to `100.0`) | Bounded heuristic screening risk score (lower is safer) |
| **Ranking** | Integer (`1, 2, 3...`) | `1` = highest-ranked screening candidate |

---

## 3. Endpoint Inventory & Request/Response Contracts

### A. Health & System Status

#### `GET /api/v1/health`
- **Purpose**: Liveness probe returning backend service health.
- **Behavior**: Read-only, synchronous.
- **Response `200 OK`**:
```json
{
  "status": "ok",
  "service": "D-DATO",
  "version": "0.1.0",
  "environment": "development"
}
```

---

### B. Planning & Asynchronous Run Lifecycle

#### `POST /api/v1/plans`
- **Purpose**: Submit a new mission planning constraint envelope and trigger asynchronous screening.
- **Behavior**: Mutating (persists Plan and queues Run), non-blocking.
- **Response `202 Accepted`**:
```json
{
  "plan_id": "64aa9c02-e7cf-42c7-99a4-2bf474563f4c",
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "status": "queued",
  "message": "Screening run queued for execution",
  "created_at": "2026-10-02T12:00:00Z"
}
```
- **Request Body (all fields optional, defaults applied automatically)**:
```json
{
  "epoch_start": "2026-10-15T12:00:00Z",
  "altitude_min_km": 500.0,
  "altitude_max_km": 600.0,
  "altitude_step_km": 25.0,
  "inclination_min_deg": 97.0,
  "inclination_max_deg": 98.0,
  "inclination_step_deg": 0.5,
  "delay_min_minutes": 0.0,
  "delay_max_minutes": 60.0,
  "delay_step_minutes": 30.0,
  "screening_days": 3,
  "reference_altitude_km": 550.0,
  "reference_inclination_deg": 97.5,
  "dv_budget_m_s": 100.0,
  "spacecraft_mass_kg": 3.0,
  "isp_seconds": 60.0,
  "fuel_weight": 0.4,
  "risk_weight": 0.6,
  "demo_mode": true
}
```

#### `GET /api/v1/runs/{run_id}`
- **Purpose**: Poll run lifecycle status, execution progress percentage, and candidate/event counts.
- **Behavior**: Strictly read-only.
- **Polling Strategy**: Poll every 500ms–1000ms until `status` is `completed` or `failed`.
- **Response `200 OK`**:
```json
{
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "plan_id": "64aa9c02-e7cf-42c7-99a4-2bf474563f4c",
  "status": "completed",
  "progress_percent": 100.0,
  "current_stage": "completed",
  "message": "Run completed successfully",
  "created_at": "2026-10-02T12:00:00Z",
  "started_at": "2026-10-02T12:00:01Z",
  "completed_at": "2026-10-02T12:00:06Z",
  "candidate_count": 45,
  "conjunction_event_count": 8,
  "ranked_candidate_count": 45
}
```

#### `GET /api/v1/plans/{plan_id}`
- **Purpose**: Retrieve stored planning constraints and input envelope.
- **Behavior**: Read-only.

#### `GET /api/v1/plans/{plan_id}/runs`
- **Purpose**: Retrieve historical screening runs associated with a plan ID.
- **Behavior**: Read-only.

---

### C. Ranked Candidates & Close-Approach Events

#### `GET /api/v1/runs/{run_id}/candidates`
- **Purpose**: Retrieve evaluated deployment candidate orbits sorted by rank (`rank ASC`).
- **Behavior**: Read-only.
- **Query Parameters**:
  - `limit`: int (default `100`, max `500`)
  - `offset`: int (default `0`)
- **Response `200 OK`**:
```json
{
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "total": 45,
  "limit": 100,
  "offset": 0,
  "candidate_count": 45,
  "status": "completed",
  "candidates": [
    {
      "candidate_id": "cand-001",
      "altitude_km": 550.0,
      "inclination_deg": 97.5,
      "raan_deg": 45.0,
      "u0_deg": 0.0,
      "deployment_delay_minutes": 0.0,
      "deployment_epoch": "2026-10-15T12:00:00Z",
      "delta_v_m_s": 0.0,
      "propellant_mass_kg": 0.0,
      "fuel_fraction": 0.0,
      "within_dv_budget": true,
      "risk_score": 3.45,
      "accepted_event_count": 0,
      "minimum_miss_distance_km": null,
      "uncertainty_level": "nominal",
      "composite_score": 0.0345,
      "rank": 1
    }
  ]
}
```

#### `GET /api/v1/runs/{run_id}/events`
- **Purpose**: Retrieve close-approach conjunction events detected during screening.
- **Behavior**: Read-only. Ordered deterministically by `tca ASC, miss_distance_km ASC`.
- **Query Parameters**:
  - `limit`: int (default `100`, max `500`)
  - `offset`: int (default `0`)
- **Response `200 OK`**:
```json
{
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "total": 8,
  "limit": 100,
  "offset": 0,
  "events": [
    {
      "event_id": "evt-001",
      "candidate_id": "cand-005",
      "debris_object_id": "deb-012",
      "debris_norad_id": "25544",
      "debris_name": "ISS (ZARYA)",
      "tca": "2026-10-15T18:42:15Z",
      "miss_distance_km": 4.12,
      "relative_velocity_km_s": 14.85,
      "threshold_km": 25.0,
      "screening_source": "ddato"
    }
  ]
}
```

---

### D. 2D Risk Heatmap Visualization

#### `GET /api/v1/runs/{run_id}/heatmap`
- **Purpose**: Deliver pre-aggregated, structured 2D matrix data for grid and contour rendering.
- **Behavior**: Read-only.
- **Query Parameters**:
  - `inclination_deg`: float (optional, filters by specific orbital inclination slice)
- **Response `200 OK`**:
```json
{
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "metric": "risk_score",
  "color_scale": "Viridis_r",
  "global_min_score": 1.20,
  "global_max_score": 48.75,
  "inclination_slices": [97.0, 97.5, 98.0],
  "layers": [
    {
      "inclination_deg": 97.5,
      "altitude_axis": [500.0, 525.0, 550.0],
      "delay_axis": [0.0, 30.0, 60.0],
      "matrix": [
        [1.20, 2.45, 5.10],
        [3.80, 4.10, 8.90],
        [6.20, 7.30, 12.40]
      ],
      "min_score": 1.20,
      "max_score": 12.40,
      "candidate_count": 9
    }
  ]
}
```

---

### E. 3D Globe & Cesium Visualization

#### `GET /api/v1/runs/{run_id}/globe`
- **Purpose**: Deliver 3D Cartesian coordinates and close-approach encounter positions for Cesium rendering.
- **Behavior**: Read-only. Coordinates are in the TEME frame in kilometers.
- **Query Parameters**:
  - `candidate_ids`: comma-separated string (e.g. `cand-1,cand-2`; defaults to top 3 ranked candidates)
  - `sample_step_seconds`: float (default `60.0`, min `1.0`; trajectory sampling frequency)
  - `max_candidates`: int (default `5`, max `20`)
  - `max_debris`: int (default `50`, max `200`)
- **Response `200 OK`**:
```json
{
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "status": "completed",
  "frame": "TEME",
  "time_scale": "UTC",
  "sample_step_seconds": 60,
  "epoch_start": "2026-10-15T12:00:00Z",
  "epoch_end": "2026-10-18T12:00:00Z",
  "candidate_count": 1,
  "debris_count": 0,
  "event_count": 1,
  "candidates": [
    {
      "candidate_id": "cand-001",
      "rank": 1,
      "altitude_km": 550.0,
      "inclination_deg": 97.5,
      "raan_deg": 45.0,
      "risk_score": 3.45,
      "within_dv_budget": true,
      "deployment_delay_minutes": 0.0,
      "deployment_epoch": "2026-10-15T12:00:00Z",
      "trajectory_start": "2026-10-15T12:00:00Z",
      "trajectory_end": "2026-10-18T12:00:00Z",
      "point_count": 2,
      "trajectory": [
        {
          "t": "2026-10-15T12:00:00Z",
          "x_km": 6928.1,
          "y_km": 0.0,
          "z_km": 0.0,
          "vx_km_s": 0.0,
          "vy_km_s": 7.58,
          "vz_km_s": 1.02
        }
      ]
    }
  ],
  "debris": [],
  "events": [
    {
      "event_id": "evt-001",
      "candidate_id": "cand-001",
      "debris_object_id": "deb-012",
      "debris_norad_id": "25544",
      "tca": "2026-10-15T18:42:15Z",
      "miss_distance_km": 4.12,
      "relative_velocity_km_s": 14.85,
      "x_km": 6850.2,
      "y_km": 124.5,
      "z_km": 890.1
    }
  ]
}
```

---

### F. External Reference Validation (SOCRATES)

#### `POST /api/v1/runs/{run_id}/validation`
- **Purpose**: Compare persisted D-DATO screening results against external SOCRATES benchmark dataset and store report.
- **Request Body (optional)**:
```json
{
  "source": "socrates",
  "tca_tolerance_seconds": 300.0,
  "miss_distance_tolerance_km": 5.0,
  "demo_mode": true
}
```
- **Response `200 OK`**:
```json
{
  "validation_id": "val-98741",
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "status": "completed",
  "source": "socrates_demo_fixture",
  "source_fetched_at": "2026-10-15T12:00:00Z",
  "validation_created_at": "2026-10-15T12:05:00Z",
  "summary": {
    "d_dato_event_count": 8,
    "external_event_count": 10,
    "matched_event_count": 7,
    "d_dato_only_count": 1,
    "external_only_count": 3,
    "external_coverage_percent": 70.0,
    "d_dato_match_rate_percent": 87.5,
    "mean_abs_tca_error_seconds": 14.2,
    "max_abs_tca_error_seconds": 28.5,
    "mean_abs_miss_distance_difference_km": 0.125,
    "max_abs_miss_distance_difference_km": 0.450
  },
  "matches": [],
  "d_dato_only": [],
  "external_only": [],
  "notes": ["NON-OPERATIONAL VALIDATION: External reference evidence only."]
}
```

#### `GET /api/v1/runs/{run_id}/validation`
- **Purpose**: Retrieve the most recently persisted validation report for a run (strictly read-only).

#### `GET /api/v1/validations/{validation_id}`
- **Purpose**: Retrieve a specific validation report directly by its ID.

---

### G. Downloadable Exports

#### `GET /api/v1/runs/{run_id}/exports/csv`
- **Purpose**: Download a deterministic ZIP archive containing typed CSV files (`plan.csv`, `candidates.csv`, `conjunction_events.csv`, and optionally `validation_summary.csv`, `validation_matches.csv`).
- **Response**: `200 OK`
- **Headers**:
  - `Content-Type: application/zip`
  - `Content-Disposition: attachment; filename="d-dato-{run_id}-export.zip"`

#### `GET /api/v1/runs/{run_id}/exports/pdf`
- **Purpose**: Download a publication-grade, multi-page executive screening PDF report generated headlessly by the backend.
- **Response**: `200 OK`
- **Headers**:
  - `Content-Type: application/pdf`
  - `Content-Disposition: attachment; filename="d-dato-{run_id}-report.pdf"`

---

## 4. Standard HTTP Error Shapes

All error responses from the API return structured JSON payloads:

### `404 Not Found`
```json
{
  "detail": {
    "code": "RUN_NOT_FOUND",
    "message": "Run 'd95c642e' was not found."
  }
}
```

### `422 Unprocessable Content` (Validation Error)
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "altitude_min_km"],
      "msg": "Value error, altitude_min_km (600.0) cannot exceed altitude_max_km (500.0)."
    }
  ]
}
```

### `500 Internal Server Error`
```json
{
  "detail": {
    "code": "EXPORT_GENERATION_ERROR",
    "message": "Failed to generate CSV export archive."
  }
}
```
