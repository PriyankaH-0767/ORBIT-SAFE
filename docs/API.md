# D-DATO REST API Reference (v1)

Base URL: `/api/v1`

D-DATO (Debris-Aware Orbit & Deployment-Window Planner) provides REST API endpoints to configure mission planning envelopes, submit non-blocking asynchronous screening runs, poll execution lifecycle status, and retrieve ranked candidate insertion options and conjunction event logs.

---

## Endpoint Summary

| Method | Endpoint | Status | Description |
|---|---|---|---|
| `GET` | `/api/v1/health` | `200 OK` | Liveness health probe returning service metadata. |
| `POST` | `/api/v1/plans` | `202 Accepted` | Create a mission plan and queue asynchronous screening execution. |
| `GET` | `/api/v1/plans/{plan_id}` | `200 OK` | Retrieve stored planning parameters and constraints. |
| `GET` | `/api/v1/plans/{plan_id}/runs` | `200 OK` | List all screening runs associated with a mission plan. |
| `GET` | `/api/v1/runs/{run_id}` | `200 OK` | Poll execution status, stage, and entity counts (strictly read-only). |
| `GET` | `/api/v1/runs/{run_id}/candidates` | `200 OK` | Retrieve ranked candidate orbits ordered by rank with pagination. |
| `GET` | `/api/v1/runs/{run_id}/events` | `200 OK` | Retrieve detected close-approach conjunction events with pagination. |
| `GET` | `/api/v1/runs/{run_id}/heatmap` | `200 OK` | Retrieve 2D risk heatmap matrix data partitioned by orbital inclination slices. |
| `GET` | `/api/v1/runs/{run_id}/globe` | `200 OK` | Retrieve 3D TEME-frame Cartesian orbital trajectories and conjunction event markers for globe visualization. |
| `POST` | `/api/v1/runs/{run_id}/validation` | `200 OK` | Execute conjunction validation against external reference source (SOCRATES) and persist report. |
| `GET` | `/api/v1/runs/{run_id}/validation` | `200 OK` | Retrieve the most recent persisted validation report for a screening run (strictly read-only). |
| `GET` | `/api/v1/validations/{validation_id}` | `200 OK` | Retrieve a specific persisted validation report directly by ID (strictly read-only). |
| `GET` | `/api/v1/runs/{run_id}/exports/csv` | `200 OK` | Download ZIP archive containing typed CSV datasets (plan, candidates, events, validation). |
| `GET` | `/api/v1/runs/{run_id}/exports/pdf` | `200 OK` | Download executive screening PDF report with run summary, constraints, candidates, events, validation, and scope notes. |


---

## 1. POST /api/v1/plans

Creates a new mission planning request and immediately queues an asynchronous screening run to the background worker.

### HTTP Status: `202 Accepted`
The endpoint returns immediately without waiting for scientific pipeline completion.

### Request Body (`PlanCreateRequest`)

All fields are optional; omitted fields automatically default to centralized D-DATO settings.

```json
{
  "epoch_start": "2026-10-02T12:00:00Z",
  "altitude_min_km": 500.0,
  "altitude_max_km": 600.0,
  "altitude_step_km": 25.0,
  "inclination_min_deg": 97.0,
  "inclination_max_deg": 98.0,
  "inclination_step_deg": 0.5,
  "raan_deg": 0.0,
  "u0_deg": 0.0,
  "delay_min_minutes": 0.0,
  "delay_max_minutes": 60.0,
  "delay_step_minutes": 60.0,
  "raan_delay_coupling_deg_per_min": 0.25068,
  "screening_days": 3,
  "reference_altitude_km": 550.0,
  "reference_inclination_deg": 97.5,
  "dv_budget_m_s": 100.0,
  "spacecraft_mass_kg": 3.0,
  "isp_seconds": 60.0,
  "fuel_weight": 0.4,
  "risk_weight": 0.6,
  "data_source": "celestrak",
  "demo_mode": true
}
```

### Response (`PlanRunAcceptedResponse`)

```json
{
  "plan_id": "64aa9c02-e7cf-42c7-99a4-2bf474563f4c",
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "status": "queued",
  "message": "Screening run queued for execution",
  "created_at": "2026-10-02T03:35:29.373467Z"
}
```

---

## 2. GET /api/v1/plans/{plan_id}

Retrieves the persisted configuration and parameter bounds of a stored mission plan.

### HTTP Status: `200 OK` (or `404 Not Found`)

### Response (`PlanResponse`)

```json
{
  "plan_id": "64aa9c02-e7cf-42c7-99a4-2bf474563f4c",
  "created_at": "2026-10-02T03:35:29.351234Z",
  "updated_at": "2026-10-02T03:35:29.351234Z",
  "epoch_start": "2026-10-02T12:00:00Z",
  "altitude_min_km": 500.0,
  "altitude_max_km": 600.0,
  "altitude_step_km": 25.0,
  "inclination_min_deg": 97.0,
  "inclination_max_deg": 98.0,
  "inclination_step_deg": 0.5,
  "raan_deg": 0.0,
  "u0_deg": 0.0,
  "delay_min_minutes": 0.0,
  "delay_max_minutes": 60.0,
  "delay_step_minutes": 60.0,
  "raan_delay_coupling_deg_per_min": 0.25068,
  "screening_days": 3,
  "reference_altitude_km": 550.0,
  "reference_inclination_deg": 97.5,
  "dv_budget_m_s": 100.0,
  "spacecraft_mass_kg": 3.0,
  "isp_seconds": 60.0,
  "fuel_weight": 0.4,
  "risk_weight": 0.6,
  "data_source": "celestrak",
  "demo_mode": true
}
```

---

## 3. GET /api/v1/plans/{plan_id}/runs

Lists all screening runs linked to a mission plan, ordered newest first (`created_at DESC`).

### HTTP Status: `200 OK` (or `404 Not Found`)

### Response (`PlanRunListResponse`)

```json
{
  "plan_id": "64aa9c02-e7cf-42c7-99a4-2bf474563f4c",
  "total": 1,
  "runs": [
    {
      "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
      "plan_id": "64aa9c02-e7cf-42c7-99a4-2bf474563f4c",
      "status": "completed",
      "progress_percent": 100.0,
      "current_stage": "completed",
      "message": "Run completed successfully",
      "created_at": "2026-10-02T03:35:29.373467Z",
      "started_at": "2026-10-02T03:35:29.385123Z",
      "completed_at": "2026-10-02T03:35:34.312984Z",
      "error_message": null,
      "candidate_count": 30,
      "conjunction_event_count": 2,
      "ranked_candidate_count": 30
    }
  ]
}
```

---

## 4. GET /api/v1/runs/{run_id}

Primary status polling endpoint for frontend clients. Strictly read-only; never triggers or restarts screening runs.

### HTTP Status: `200 OK` (or `404 Not Found`)

### Polling Semantics
- **Queued**: `started_at` is `null`, `completed_at` is `null`, `progress_percent` is `0.0`.
- **Running**: `started_at` is present, `completed_at` is `null`, `progress_percent` reflects stage (5% ingestion, 35% screening, 85% ranking).
- **Completed**: `completed_at` is present, `progress_percent` is `100.0`, `error_message` is `null`.
- **Failed**: `completed_at` is present, `error_message` is non-null.

### Response (`RunStatusResponse`)

```json
{
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "plan_id": "64aa9c02-e7cf-42c7-99a4-2bf474563f4c",
  "status": "completed",
  "progress_percent": 100.0,
  "current_stage": "completed",
  "message": "Run completed successfully",
  "created_at": "2026-10-02T03:35:29.373467Z",
  "started_at": "2026-10-02T03:35:29.385123Z",
  "completed_at": "2026-10-02T03:35:34.312984Z",
  "error_message": null,
  "candidate_count": 30,
  "conjunction_event_count": 2,
  "ranked_candidate_count": 30
}
```

---

## 5. GET /api/v1/runs/{run_id}/candidates

Retrieves evaluated candidate deployment orbits for a screening run, ordered by `rank ASC`.

### Query Parameters
- `limit` (int, default: 100, min: 1, max: 300): Number of candidates to return.
- `offset` (int, default: 0, min: 0): Number of candidates to skip.

### Result Availability Behavior
- If run is still queued or running, returns `HTTP 200 OK` with `total: 0` and `candidates: []` without blocking.
- If run does not exist, returns `HTTP 404 Not Found`.

### Response (`CandidateResultsResponse`)

```json
{
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "total": 30,
  "limit": 5,
  "offset": 0,
  "candidate_count": 30,
  "status": "completed",
  "candidates": [
    {
      "candidate_id": "37817e04-0fca-4073-83a0-b130f929d5a1",
      "altitude_km": 550.0,
      "inclination_deg": 97.5,
      "raan_deg": 0.0,
      "u0_deg": 0.0,
      "deployment_delay_minutes": 0.0,
      "deployment_epoch": "2026-10-02T12:00:00Z",
      "delta_v_m_s": 0.0,
      "propellant_mass_kg": 0.0,
      "fuel_fraction": 0.0,
      "within_dv_budget": true,
      "risk_score": 0.0,
      "accepted_event_count": 1,
      "minimum_miss_distance_km": 13.749,
      "uncertainty_level": "nominal",
      "normalized_fuel_cost": null,
      "normalized_risk_cost": null,
      "composite_score": null,
      "rank": 1
    }
  ]
}
```

---

## 6. GET /api/v1/runs/{run_id}/events

Retrieves close-approach conjunction events detected during screening, ordered by:
1. `tca` ascending
2. `miss_distance_km` ascending
3. `candidate_id` ascending
4. `debris_object_id` ascending

### Query Parameters
- `limit` (int, default: 100, min: 1, max: 1000): Number of events to return.
- `offset` (int, default: 0, min: 0): Number of events to skip.

### Response (`EventResultsResponse`)

```json
{
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "total": 2,
  "limit": 100,
  "offset": 0,
  "event_count": 2,
  "status": "completed",
  "events": [
    {
      "id": "4606a1d2-803a-41c3-b853-25c5ce7ac1d2",
      "candidate_id": "37817e04-0fca-4073-83a0-b130f929d5a1",
      "debris_object_id": "19bfa6a1-a79a-4c91-b663-0d2d3a39e80a",
      "debris_norad_id": "25544",
      "tca": "2026-10-03T04:12:35.120000Z",
      "miss_distance_km": 13.749,
      "relative_velocity_km_s": 5.803,
      "threshold_km": 25.0,
      "screening_source": "ddato"
    }
  ]
}
```

---

## 7. GET /api/v1/runs/{run_id}/heatmap

Retrieves 2D risk density matrices over the candidate grid for visualization in the future React/Plotly frontend.

### Semantics & Coordinates
- **X axis**: `delay_minutes` (deployment delay in minutes)
- **Y axis**: `altitude_km` (circular orbit altitude in km)
- **Slice dimension**: `inclination_deg` (each distinct inclination produces one 2D layer)
- **Metric**: Persisted `risk_score` (canonical 0–100 scale). No candidate generation, screening, or ranking recomputation is executed.
- **Null-cell semantics**: If a candidate coordinate is missing from the persisted result set, that grid location in `values[row][col]` is represented as `null`. Values are strictly not interpolated.
- **Read-only**: Does not restart runs, queue workers, or perform external network calls.

### Query Parameters
- `inclination_deg` (float, optional, default: None): Slices the heatmap to return only the layer matching this inclination in degrees. If omitted, returns all inclination layers.

### HTTP Status Codes
- `200 OK`: Run exists. If the run is queued or running without persisted results yet, returns 200 with `layers = []` and `total_candidates = 0`. If `inclination_deg` does not match any layer, returns 200 with `layers = []`.
- `404 Not Found`: `run_id` does not exist in the database.
- `422 Unprocessable Entity`: `inclination_deg` is non-numeric or malformed.
- `500 Internal Server Error`: Unexpected internal error.

### Example Request
```http
GET /api/v1/runs/d95c642e-87b1-4a03-b705-bbf909edc1fb/heatmap?inclination_deg=97.5
```

### Example Response (`HeatmapResponse`)
```json
{
  "run_id": "d95c642e-87b1-4a03-b705-bbf909edc1fb",
  "status": "completed",
  "metric": "risk_score",
  "x_axis": "delay_minutes",
  "y_axis": "altitude_km",
  "inclination_values_deg": [97.5],
  "layers": [
    {
      "inclination_deg": 97.5,
      "altitude_values_km": [550.0, 575.0, 600.0],
      "delay_values_minutes": [0.0, 60.0],
      "values": [
        [0.0, 0.0],
        [0.0, 0.0],
        [0.0, 0.0]
      ],
      "cells": [
        {
          "candidate_id": "f2fc7c93-9195-4f60-8673-654cc6905a0d",
          "altitude_km": 550.0,
          "inclination_deg": 97.5,
          "delay_minutes": 0.0,
          "risk_score": 0.0,
          "rank": 1,
          "delta_v_m_s": 25.14,
          "within_dv_budget": true,
          "accepted_event_count": 0,
          "minimum_miss_distance_km": null,
          "uncertainty_level": "nominal"
        }
      ]
    }
  ],
  "total_candidates": 6,
  "populated_cells": 6,
  "min_risk_score": 0.0,
  "max_risk_score": 0.0
}
```

---

## 8. GET /api/v1/runs/{run_id}/globe

Retrieves TEME-frame Cartesian orbital trajectories for ranked candidate orbits and associated debris objects in a D-DATO screening run, plus conjunction event markers for 3D globe / Cesium visualization.

Strictly read-only and offline: does not trigger pipeline execution, worker submission, or external network calls.

### HTTP Status: `200 OK` (or `404 Not Found`, `422 Unprocessable Entity`)

### Query Parameters

| Parameter | Type | Default | Bounds | Description |
|---|---|---|---|---|
| `candidate_ids` | `string` (query) | `None` | Optional comma-separated | Comma-separated candidate database IDs to visualize. If provided, returns only these candidates (must belong to the run; unknown ID -> 404 `CANDIDATE_NOT_FOUND`; malformed/empty -> 422 `INVALID_CANDIDATE_IDS`). If omitted, returns top-ranked candidates up to `max_candidates`. |
| `sample_step_seconds` | `integer` (query) | `300` | `30`–`3600` | Trajectory sampling interval in seconds. Default 300 (5 min). |
| `max_candidates` | `integer` (query) | `20` | `1`–`50` | Maximum number of candidate tracks to return when `candidate_ids` is omitted. Ordered by rank ASC. |
| `max_debris` | `integer` (query) | `25` | `1`–`100` | Maximum number of debris tracks to return. Prioritizes debris participating in events, then fills remaining slots deterministically ordered by `norad_id ASC, id ASC`. |

### Coordinate & Physics Contract
- **Coordinate Frame**: `TEME` (True Equator Mean Equinox). Not labeled ECEF.
- **Time Scale**: `UTC` (ISO 8601 with timezone).
- **Position Units**: `km`.
- **Velocity Units**: `km/s`.
- **Candidate Trajectories**:
  - Each candidate trajectory begins strictly at its `deployment_epoch` (`plan.epoch_start + deployment_delay_minutes`).
  - No candidate points are generated before deployment.
  - Samples cover `[deployment_epoch, deployment_epoch + screening_days]`.
  - Propagated using `CircularJ2` model.
- **Debris Trajectories**:
  - Debris trajectories cover the mission screening window `[plan.epoch_start, plan.epoch_start + screening_days]`.
  - Propagated using `SGP4` model.
- **Conjunction Event Markers**:
  - Filtered strictly to the selected candidate and included debris subset.
  - Position (`x_km`, `y_km`, `z_km`) is evaluated by propagating the threatening debris object via `SGP4` at the exact persisted `tca`.

### Response (`GlobeResponse`)

```json
{
  "run_id": "481dc7f0-505f-4278-9b47-82e3fe6e18ff",
  "status": "completed",
  "frame": "TEME",
  "time_scale": "UTC",
  "sample_step_seconds": 3600,
  "epoch_start": "2026-10-02T12:00:00Z",
  "epoch_end": "2026-10-05T12:00:00Z",
  "candidate_count": 2,
  "debris_count": 1,
  "event_count": 1,
  "candidates": [
    {
      "candidate_id": "a6fed8f9-f140-498f-8db3-ad94de861ff6",
      "rank": 1,
      "altitude_km": 550.0,
      "inclination_deg": 97.5,
      "raan_deg": 0.0,
      "risk_score": 12.5,
      "within_dv_budget": true,
      "deployment_delay_minutes": 0.0,
      "deployment_epoch": "2026-10-02T12:00:00Z",
      "trajectory_start": "2026-10-02T12:00:00Z",
      "trajectory_end": "2026-10-05T12:00:00Z",
      "point_count": 73,
      "trajectory": [
        {
          "t": "2026-10-02T12:00:00Z",
          "x_km": 6928.137,
          "y_km": 0.000,
          "z_km": 0.000,
          "vx_km_s": 0.0000,
          "vy_km_s": 0.9928,
          "vz_km_s": 7.5148
        }
      ]
    }
  ],
  "debris": [
    {
      "norad_id": "700001",
      "object_name": "TEST DEBRIS",
      "debris_db_id": "deb-001",
      "point_count": 73,
      "trajectory": [
        {
          "t": "2026-10-02T12:00:00Z",
          "x_km": 6850.123,
          "y_km": 120.456,
          "z_km": -300.789,
          "vx_km_s": 0.1234,
          "vy_km_s": 7.4500,
          "vz_km_s": 0.0500
        }
      ]
    }
  ],
  "events": [
    {
      "event_id": "bd96754c-789a-4123-bcde-0123456789ab",
      "candidate_id": "a6fed8f9-f140-498f-8db3-ad94de861ff6",
      "debris_object_id": "deb-001",
      "debris_norad_id": "700001",
      "tca": "2026-10-04T03:29:28.753588Z",
      "miss_distance_km": 13.749,
      "relative_velocity_km_s": 14.2,
      "x_km": 269.236,
      "y_km": 973.079,
      "z_km": -6842.659
    }
  ]
}
```

---

## 9. External Validation Endpoints (Phase P16)

> [!IMPORTANT]
> **Non-Operational Scientific & Product Positioning**:
> Validation means "D-DATO screening result compared with an independently supplied/queried external close-approach source (specifically SOCRATES)."
> It does **NOT** represent certified flight safety, operational conjunction assessment, true collision probability, CDM generation, maneuver planning, or launch COLA.
> A SOCRATES validation event is external reference evidence; D-DATO's own conjunction events remain the primary screening output. Screening algorithms are never rerun during validation.

### `POST /api/v1/runs/{run_id}/validation`
Triggers an external validation comparison for a completed screening run against external reference evidence.

#### Request Body (`ValidationExecutionRequest`)
```json
{
  "source": "socrates",
  "tca_tolerance_seconds": 300.0,
  "miss_distance_tolerance_km": 5.0,
  "demo_mode": true
}
```

* `source` (string, default: `"socrates"`): External reference dataset. Currently supported: `"socrates"`.
* `tca_tolerance_seconds` (float, default: `300.0`): Maximum allowable absolute difference in Time of Closest Approach for event pairing (> 0).
* `miss_distance_tolerance_km` (float, default: `5.0`): Maximum allowable absolute difference in miss distance for event pairing (> 0).
* `demo_mode` (boolean | null): When true, forces offline deterministic bundled fixture usage (`socrates_demo_fixture`) with zero external network connectivity.

#### Matching Hierarchy
1. Canonical debris NORAD catalog identifier agreement (exact normalized match).
2. TCA absolute difference $\le$ `tca_tolerance_seconds`.
3. Miss-distance absolute difference $\le$ `miss_distance_tolerance_km` (where external miss distance exists).
4. Unambiguous 1-to-1 greedy assignment sorted by smallest absolute TCA error, then smallest absolute miss distance error.

#### Response (`ValidationResponse`)
```json
{
  "validation_id": "val-3857eb9b-1790923456",
  "run_id": "3857eb9b-9acf-409f-876a-2589ad373c20",
  "status": "completed",
  "source": "socrates_demo_fixture",
  "source_fetched_at": "2026-10-02T00:00:00Z",
  "validation_created_at": "2026-10-02T06:44:16.728472Z",
  "summary": {
    "d_dato_event_count": 2,
    "external_event_count": 5,
    "matched_event_count": 1,
    "d_dato_only_count": 1,
    "external_only_count": 4,
    "external_coverage_percent": 20.0,
    "d_dato_match_rate_percent": 50.0,
    "mean_abs_tca_error_seconds": 0.0,
    "max_abs_tca_error_seconds": 0.0,
    "mean_abs_miss_distance_difference_km": 0.0005,
    "max_abs_miss_distance_difference_km": 0.0005
  },
  "matches": [
    {
      "d_dato_event_id": "cefa7738-d74f-4970-a516-f92c77503805",
      "external_event_id": "SOC-DEMO-001",
      "candidate_id": "7abcd812-3f3f-4001-80e4-e82220b02133",
      "debris_norad_id": "700001",
      "tca_d_dato": "2026-10-04T03:29:28.753588Z",
      "tca_external": "2026-10-04T03:29:28.753588Z",
      "tca_error_seconds": 0.0,
      "miss_distance_d_dato_km": 13.7485,
      "miss_distance_external_km": 13.749,
      "miss_distance_difference_km": -0.0005,
      "match_criteria": ["debris_norad_id", "tca_tolerance", "miss_distance_tolerance"]
    }
  ],
  "d_dato_only": [
    {
      "d_dato_event_id": "2e6905cb-5899-4452-99a4-df164c60b37d",
      "candidate_id": "7051b726-ce6e-4f82-a041-2f5290313a86",
      "debris_norad_id": "700001",
      "tca": "2026-10-04T04:17:36.944852Z",
      "miss_distance_km": 19.0394,
      "relative_velocity_km_s": 14.1,
      "notes": "No matching external reference event within configured tolerances."
    }
  ],
  "external_only": [
    {
      "external_event_id": "SOC-DEMO-002",
      "debris_norad_id": "700001",
      "tca": "2026-10-04T04:17:50Z",
      "miss_distance_km": 18.5,
      "relative_velocity_km_s": 14.1,
      "candidate_identifier": "CAND_SSO_02",
      "notes": "No matching D-DATO conjunction event within configured tolerances."
    }
  ],
  "notes": [
    "NON-OPERATIONAL VALIDATION: D-DATO conjunction validation comparison is external reference evidence only. It does NOT represent certified flight safety, operational conjunction assessment, true collision probability, CDM generation, maneuver planning, or launch COLA.",
    "Validation reference source: socrates_demo_fixture (dataset: socrates).",
    "Matching criteria applied: canonical debris NORAD identifier, TCA tolerance <= 10.0s, miss distance tolerance <= 5.0km.",
    "External reference snapshot epoch: 2026-10-02T00:00:00Z."
  ]
}
```

---

### `GET /api/v1/runs/{run_id}/validation`
Retrieves the most recent persisted validation report for a screening run.
* **HTTP Status**: `200 OK`
* Strictly read-only; does NOT query external networks or rerun screening.

---

### `GET /api/v1/validations/{validation_id}`
Directly retrieves a specific persisted validation report by ID.
* **HTTP Status**: `200 OK`
* Strictly read-only.

---

## 10. Error Handling

### HTTP 404 Not Found
When a requested plan or run is not found:
```json
{
  "detail": {
    "code": "PLAN_NOT_FOUND",
    "message": "Plan 'non-existent-id' was not found."
  }
}
```
Or for an unknown run:
```json
{
  "detail": {
    "code": "RUN_NOT_FOUND",
    "message": "Run 'non-existent-id' was not found."
  }
}
Or for an unknown validation record:
```json
{
  "detail": {
    "code": "VALIDATION_NOT_FOUND",
    "message": "Validation 'non-existent-id' was not found."
  }
}
```

### HTTP 422 Unprocessable Entity
Validation errors adhere to standard FastAPI / Pydantic schema validation:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Value error, altitude_min_km (600.0) cannot exceed altitude_max_km (500.0).",
      "input": { ... }
    }
  ]
}
```
Or for invalid validation tolerances:
```json
{
  "detail": {
    "code": "INVALID_VALIDATION_REQUEST",
    "message": "tca_tolerance_seconds must be positive (> 0), got -10.0."
  }
}
```

### HTTP 503 Service Unavailable
When an external validation source is offline and no cached or demo fixture fallback is available:
```json
{
  "detail": {
    "code": "VALIDATION_SOURCE_UNAVAILABLE",
    "message": "SOCRATES validation source is not enabled (SOCRATES_ENABLED=False) and no cached validation reference data is available."
  }
}
```

---

## 11. GET /api/v1/runs/{run_id}/exports/csv

Exports persisted screening plan parameters, evaluated candidate orbits, close-approach conjunction events, and external validation comparison results (when available) as a structured ZIP archive containing separate, typed CSV files.

### HTTP Status: `200 OK` (or `404 Not Found`, `500 Internal Server Error`)

### Response Headers
- `Content-Type: application/zip`
- `Content-Disposition: attachment; filename="d-dato-{run_id}-export.zip"`

### Read-Only / No Recomputation Guarantee
The export endpoint is strictly a serialization layer over persisted database entities. It does NOT rerun candidate generation, orbital propagation, conjunction screening, risk scoring, ranking, or external validation queries.

### ZIP Archive Structure
The returned archive contains files in deterministic order:
1. `plan.csv`: 1 row containing the persisted mission plan configuration.
2. `candidates.csv`: 1 row per evaluated Candidate orbit, ordered by `rank ASC, candidate_id ASC`.
3. `conjunction_events.csv`: 1 row per close-approach ConjunctionEvent, ordered by `tca ASC, miss_distance_km ASC, candidate_id ASC, debris_object_id ASC`.
4. `validation_summary.csv`: (*Included only when a ValidationRecord exists*) 1 row containing aggregate validation comparison metrics.
5. `validation_matches.csv`: (*Included only when a ValidationRecord exists*) Paired matches between D-DATO and external reference events.

### Column Specifications

#### `plan.csv`
`plan_id`, `run_id`, `created_at`, `epoch_start`, `altitude_min_km`, `altitude_max_km`, `altitude_step_km`, `inclination_min_deg`, `inclination_max_deg`, `inclination_step_deg`, `raan_deg`, `u0_deg`, `delay_min_minutes`, `delay_max_minutes`, `delay_step_minutes`, `raan_delay_coupling_deg_per_min`, `screening_days`, `reference_altitude_km`, `reference_inclination_deg`, `dv_budget_m_s`, `spacecraft_mass_kg`, `isp_seconds`, `fuel_weight`, `risk_weight`, `data_source`, `demo_mode`, `export_generated_at`

#### `candidates.csv`
`candidate_id`, `run_id`, `rank`, `altitude_km`, `inclination_deg`, `raan_deg`, `u0_deg`, `deployment_delay_minutes`, `deployment_epoch`, `delta_v_m_s`, `propellant_mass_kg`, `fuel_fraction`, `within_dv_budget`, `risk_score`, `accepted_event_count`, `minimum_miss_distance_km`, `uncertainty_level`, `composite_score`

#### `conjunction_events.csv`
`event_id`, `run_id`, `candidate_id`, `debris_object_id`, `debris_norad_id`, `tca`, `miss_distance_km`, `relative_velocity_km_s`, `threshold_km`, `screening_source`

#### `validation_summary.csv`
`validation_id`, `run_id`, `status`, `source`, `source_fetched_at`, `validation_created_at`, `d_dato_event_count`, `external_event_count`, `matched_event_count`, `d_dato_only_count`, `external_only_count`, `external_coverage_percent`, `d_dato_match_rate_percent`, `mean_abs_tca_error_seconds`, `max_abs_tca_error_seconds`, `mean_abs_miss_distance_difference_km`, `max_abs_miss_distance_difference_km`

#### `validation_matches.csv`
`d_dato_event_id`, `external_event_id`, `candidate_id`, `debris_norad_id`, `tca_d_dato`, `tca_external`, `tca_error_seconds`, `miss_distance_d_dato_km`, `miss_distance_external_km`, `miss_distance_difference_km`, `match_criteria`

---

## 12. GET /api/v1/runs/{run_id}/exports/pdf

Generates and streams a comprehensive executive screening report in PDF format based strictly on persisted database results.

### HTTP Status: `200 OK` (or `404 Not Found`, `500 Internal Server Error`)

### Response Headers
- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename="d-dato-{run_id}-report.pdf"`

### Report Contents and Structure
The PDF report follows a clean, publication-grade multi-page layout containing 7 structured sections:
1. **Title & Non-Operational Notice**:
   Prominent banner explicitly stating:
   *"D-DATO is an early-stage screening/planning aid. It is not a certified collision-probability system, operational conjunction assessment tool, maneuver planner, CDM generator, or launch COLA system."*
2. **Section 1 — Run Summary**: Execution IDs, lifecycle state, timestamps, candidate counts, and close-approach event totals.
3. **Section 2 — Planning Inputs**: Configured parameter bounds, deployment delays, reference orbit, propulsion constraints, and objective weighting.
4. **Section 3 — Ranked Candidates**: Formatted table of top 20 candidate orbits ordered by rank (labeled *"Highest-ranked screening candidate"*; does not claim optimality).
5. **Section 4 — Close-Approach Conjunction Events**: Formatted table of close-approach events detected within screening thresholds. Handles zero-event runs gracefully.
6. **Section 5 — External Reference Comparison (SOCRATES)**: Comparative metrics against external benchmark data (omitted when no validation record exists).
7. **Section 6 — Data Age and Provenance**: Catalog source, snapshot timestamps, tracked object counts, and export generation timestamps.
8. **Section 7 — Methodological Scope and Limitations**: Summary of J2 propagation, SGP4 debris kinematics, two-pass screening, and non-operational boundaries.

---

## 13. Health Check Probe

### `GET /api/v1/health`
Exact JSON payload:
```json
{
  "status": "ok",
  "service": "D-DATO",
  "version": "0.1.0",
  "environment": "development"
}
```


