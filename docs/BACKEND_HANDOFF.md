# D-DATO Backend Handoff Document

**Project**: D-DATO (Debris-Aware Orbit & Deployment-Window Planner)  
**Smart India Hackathon 2026** | **Problem Statement**: 26209  
**Backend Owner**: Person 1  
**Target Recipient**: Person 2 (Frontend Integration & UI Development)  
**Handoff Date**: October 2, 2026  
**Status**: Feature-Frozen, Hardened, Contract-Locked (Phase P0–P18 Complete)

---

## 1. Project Status

The D-DATO backend is **complete, verified, hardened, and feature-frozen**. All phases from P0 through P18 have been implemented, tested, and validated against authoritative astrodynamics requirements. The backend is fully ready for Person 2 frontend integration.

No frontend code has been written; the application boundary is strictly defined by the versioned HTTP REST API (`/api/v1/*`).

---

## 2. Current Test Baseline

- **Total Automated Tests**: **387 passed**
- **Failures / Errors**: **0 failed**
- **Warnings**: **1 warning** (classified below under Known Warnings)
- **Suite Execution Duration**: ~251.86s (full test suite across unit and integration tests)
- **Smoke Test Status**: **PASS** (100% offline verification across all frozen endpoints)

---

## 3. Feature Surface

The frozen backend exposes 13 stable REST endpoints across 6 core functional areas:

1. **Health & Status**:
   - `GET /api/v1/health`: Instant service health, environment, and version indicator.

2. **Planning & Asynchronous Run Execution**:
   - `POST /api/v1/plans`: Accepts mission constraints (altitude, inclination, delay ranges, delta-v budget, spacecraft mass, Isp, fuel/risk weights) and queues an asynchronous screening run (returns HTTP `202 Accepted` with `plan_id` and `run_id`).
   - `GET /api/v1/plans/{plan_id}`: Retrieves persisted mission parameters.
   - `GET /api/v1/plans/{plan_id}/runs`: Lists execution history and run metadata for a plan.
   - `GET /api/v1/runs/{run_id}`: Pollable endpoint for tracking lifecycle status (`queued`, `running`, `completed`, `failed`, `cancelled`), stage, progress percentage, and candidate counts.

3. **Candidate Results & Conjunction Events**:
   - `GET /api/v1/runs/{run_id}/candidates`: Paginated list of deployment candidates ranked deterministically by composite score, delta-v budget compliance, and close-approach encounters.
   - `GET /api/v1/runs/{run_id}/events`: Paginated list of detected close approaches with Time of Closest Approach (TCA), miss distance in km, and relative velocity in km/s.

4. **2D Risk Heatmap**:
   - `GET /api/v1/runs/{run_id}/heatmap`: Pre-computed 2D risk density matrices (delay vs. altitude) organized by discrete inclination slices for Plotly/React heatmap components. Supports `inclination_deg` query parameter.

5. **3D Globe Trajectory Coordinates**:
   - `GET /api/v1/runs/{run_id}/globe`: Cartesian TEME-frame positions (km) and velocities (km/s) sampled at configurable time steps for satellite candidates and screened debris orbits. Includes exact 3D Cartesian SGP4 positions for all detected conjunction markers at TCA for Cesium/React rendering.

6. **External Reference Validation**:
   - `POST /api/v1/runs/{run_id}/validation`: Triggers audit comparison against external reference datasets (specifically SOCRATES) using configurable TCA and miss-distance tolerances.
   - `GET /api/v1/runs/{run_id}/validation`: Retrieves the latest validation comparison for a run.
   - `GET /api/v1/validations/{validation_id}`: Direct lookup by validation record identifier.

7. **Data & Report Exports**:
   - `GET /api/v1/runs/{run_id}/exports/csv`: Returns a streaming ZIP archive containing 5 structured CSV files (`plan.csv`, `candidates.csv`, `conjunction_events.csv`, `validation_summary.csv`, `validation_matches.csv`).
   - `GET /api/v1/runs/{run_id}/exports/pdf`: Returns a downloadable multi-page PDF summary report generated headlessly via ReportLab with executive summary, tables, and audit disclaimers.

---

## 4. Scientific Architecture & Algorithms

All scientific logic is strictly isolated in the backend:
- **Candidate Orbit Model**: Circular orbit model with Earth J2 secular perturbation drift ($\dot{\Omega}$ RAAN precession, $\dot{\omega}$ apsidal drift, mean motion correction).
- **Debris Ephemeris Propagation**: High-precision SGP4 propagator evaluating True Equator, Mean Equinox (TEME) state vectors from Two-Line Element (TLE) sets.
- **Two-Pass Conjunction Screening**:
  1. *Coarse Pass*: Fast spatial bounding box filtering in perigee/apogee altitude.
  2. *Fine Pass*: Fixed-step propagation with Golden-Section numerical search for exact Time of Closest Approach (TCA) refinement.
- **Maneuver & Delta-V Budgeting**: Circular coplanar altitude transfers and plane changes via Tsiolkovsky rocket equation.
- **Bounded Composite Risk Heuristic**: Sigmoidal/exponential miss-distance scaling yielding an intuitive 0–100 risk metric.
- **Deterministic Multi-Objective Ranking**: Normalized composite score balancing delta-v consumption and debris risk, with hard delta-v budget compliance flags.

---

## 5. Data Sources & Provenance

- **CelesTrak & Space-Track**: Configurable remote catalog ingestion with local filesystem SHA-256 caching and minimum fetch interval throttling (2-hour minimum).
- **SOCRATES Reference Adapter**: Validation comparison against SOCRATES conjunction datasets (disabled remotely by default, backed by offline cache and synthetic fixtures).
- **Offline Demo Mode**: Completely self-contained offline demo fixtures (`demo_data/demo_catalog.json`, `demo_data/tle/demo_catalog.tle`, `demo_data/validation/socrates_fixture.json`).
- **Provenance Tagging**: Every record is tagged with data source and provenance (`celestrak`, `spacetrack`, `socrates_live`, `socrates_cache`, or `socrates_demo_fixture`).

---

## 6. Frontend API Contract Link

The authoritative frontend integration contract is documented in:
[FRONTEND_API_CONTRACT.md](file:///e:/D-DATO/docs/FRONTEND_API_CONTRACT.md)

### Frontend Integration Rules (Non-Negotiable):
1. **Frontend Must Never Implement Orbital Mechanics**: All SGP4 propagation, J2 drift, TCA refinement, coordinate transformations, and delta-v calculations belong strictly to the backend.
2. **Frontend Must Not Recalculate Risk or Rankings**: Rankings, scores, and risk values are already computed and persisted in the database.
3. **Polling Pattern**: Frontend should submit `POST /api/v1/plans`, extract `run_id`, and poll `GET /api/v1/runs/{run_id}` until `status == "completed"`.
4. **Standard Units**:
   - Angles: degrees (`deg`)
   - Altitudes & Distances: kilometers (`km`)
   - Delta-V: meters per second (`m/s`)
   - Velocities: kilometers per second (`km/s`)
   - Timestamps: ISO-8601 UTC strings (`YYYY-MM-DDTHH:MM:SSZ`)
   - Coordinates: Cartesian TEME frame (`x_km`, `y_km`, `z_km`)

---

## 7. Explicit Non-Operational Positioning

> [!CAUTION]
> **MANDATORY DISCLAIMER FOR ALL USER INTERFACES**:  
> D-DATO is an **early-stage mission planning and trajectory screening aid**.  
> It does **NOT** provide:
> - Certified spacecraft flight safety
> - True collision probability ($P_c$) calculations
> - Operational Conjunction Assessment (CA)
> - Conjunction Data Message (CDM) generation
> - Autonomous maneuver approval
> - Optimal trajectory guarantees
> - Launch Collision On Orbit Avoidance (COLA) certification
>
> Frontend UI text, tooltips, cards, and headers must use approved terminology:
> - *Use*: "Candidate Orbit", "Screened Close Approach", "Ranked Candidate", "Early-Stage Planning Aid", "Reference Comparison".
> - *Avoid*: "Collision Probability", "Certified Safe", "Operational Maneuver", "Optimal Orbit", "Launch COLA".

---

## 8. Known Warnings & Limitations

### 1. Warning Inventory (1 Total)
- **Warning**: `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead.`
- **Classification**: Third-party dependency deprecation notice within Starlette/FastAPI TestClient internals.
- **Impact**: Zero runtime impact on application or production code (affects only test client harness).
- **Resolution Policy**: Preserved to avoid upgrading unrelated packages and maintain pinned dependency stability.

### 2. Operational Limitations
- **Spherical / Circular Orbit Assumption for Candidates**: Candidates are modeled as near-circular Low Earth Orbits with J2 drift.
- **Offline Demo Mode by Default**: Out-of-the-box configuration runs completely offline with bundled fixtures. Live CelesTrak or SOCRATES queries require explicit configuration in `.env`.
- **Validation Scope**: Validation compares screening outputs against external reference data; it does not replace or modify D-DATO's internal screening results.

---

## 9. How to Run & Verify

### 1. Start the API Server
```powershell
.\backend\venv\Scripts\uvicorn.exe app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```
API Documentation:
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### 2. Run Automated Regression Tests
```powershell
# Quiet full regression
.\backend\venv\Scripts\pytest.exe -q

# Verbose regression
.\backend\venv\Scripts\pytest.exe -v
```

### 3. Run End-to-End Offline Smoke Test
```powershell
.\backend\venv\Scripts\python.exe backend\scripts\smoke_test_backend.py
```
*Expected output: All 13 endpoints verified offline, mock socket guard confirmed, performance timings reported, final status: `PASS`.*

### 4. Run Standalone Demonstration Scripts
- **P13 API Demo**: `.\backend\venv\Scripts\python.exe backend\scripts\demo_p13_api.py`
- **P14 Heatmap Demo**: `.\backend\venv\Scripts\python.exe backend\scripts\demo_p14_heatmap.py`
- **P15 3D Globe Demo**: `.\backend\venv\Scripts\python.exe backend\scripts\demo_p15_globe.py`
- **P16 Validation Demo**: `.\backend\venv\Scripts\python.exe backend\scripts\demo_p16_validation.py`
- **P17 Exports Demo**: `.\backend\venv\Scripts\python.exe backend\scripts\demo_p17_exports.py`
