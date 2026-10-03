# D-DATO: Debris-Aware Orbit & Deployment-Window Planner

D-DATO is an astrodynamics-driven trajectory planning and risk screening platform designed to evaluate candidate satellite deployment windows and orbits against cataloged orbital debris.

Smart India Hackathon 2026 | Problem Statement 26209  
**Backend Owner (Person 1): Final Hardened & Contract-Frozen Release (Phase P0–P18)**

---

## Non-Operational Disclaimer & Scope

> [!IMPORTANT]
> **NON-OPERATIONAL POSITIONING & SCIENTIFIC SCOPE**:  
> D-DATO is an early-stage mission screening, orbit selection, and deployment-window planning aid. It does **NOT** provide:
> - Certified spacecraft flight safety or operational collision avoidance
> - True collision probability ($P_c$) calculations
> - Operational Conjunction Assessment (CA) or Conjunction Data Message (CDM) generation
> - Autonomous maneuver approval or commands
> - Globally optimal trajectory guarantees
> - Launch Collision On Orbit Avoidance (COLA) certification
>
> All candidate evaluations, close-approach screenings, risk scoring metrics, and external reference comparisons (e.g. SOCRATES) represent decision-support screening evidence only.

---

## Backend Quick Start

This guide uses standard Windows PowerShell commands for the verified development environment.

### 1. Python Version
Requires **Python 3.10+** (verified and benchmarked on **Python 3.13.15 64-bit**).

### 2. Virtual Environment Creation
From the project root repository directory:
```powershell
python -m venv backend\venv
```

### 3. Dependency Installation
Install verified direct dependencies (including pinned `reportlab==5.0.1`):
```powershell
.\backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```
To verify clean dependencies without conflicts:
```powershell
.\backend\venv\Scripts\python.exe -m pip check
```

### 4. Environment Configuration
Copy the provided environment template:
```powershell
copy .env.example .env
```
*(Default settings enable offline demo mode out-of-the-box with SQLite database `d_dato.db`, no external credentials required).*

### 5. Starting the FastAPI Backend
Start the Uvicorn development server:
```powershell
.\backend\venv\Scripts\uvicorn.exe app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

### 6. Interactive OpenAPI Documentation
Open your browser to inspect or test the API:
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI JSON Schema**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

### 7. Running the Automated Test Suite
Run the full test suite with quiet regression output:
```powershell
.\backend\venv\Scripts\pytest.exe -q
```
Or run specific test categories:
```powershell
# Unit test suite
.\backend\venv\Scripts\pytest.exe backend\tests\unit -q

# Integration test suite
.\backend\venv\Scripts\pytest.exe backend\tests\integration -q
```

### 8. Running the End-to-End Backend Smoke Test
Run the offline end-to-end verification script covering all frozen endpoints (P1–P17):
```powershell
.\backend\venv\Scripts\python.exe backend\scripts\smoke_test_backend.py
```
This script exercises offline plan submission, polling, candidate retrieval, event queries, heatmap generation, 3D globe coordinates, external reference validation, CSV ZIP export, PDF generation, and confirms no scientific recomputation occurs on read-only endpoints.

### 9. Demo Mode & Offline Execution
D-DATO is engineered for **100% offline reproducibility**:
- **Offline TLE and Catalog Fixtures**: Bundled in `demo_data/` (including 6-digit NORAD catalog IDs).
- **Offline Reference Validation**: Bundled SOCRATES fixture in `backend/app/data/socrates_demo.py`.
- **Demo Scripts**:
  - `backend/scripts/demo_p13_api.py` (REST API lifecycle demo)
  - `backend/scripts/demo_p14_heatmap.py` (2D risk density matrix demo)
  - `backend/scripts/demo_p15_globe.py` (3D TEME-frame globe trajectories demo)
  - `backend/scripts/demo_p16_validation.py` (External reference validation comparison demo)
  - `backend/scripts/demo_p17_exports.py` (CSV ZIP & PDF report generation demo)

All demo scripts run completely offline and clean up temporary database and file resources on exit.

---

## Person 1 Responsibility: Backend Architecture

The backend implements the end-to-end data, astrodynamics, and API pipeline:
- **Orbital Mechanics Engine**: SGP4 ephemeris propagation, Keplerian-Cartesian conversions, J2 secular perturbation modeling.
- **Delta-V & Maneuver Budgeting**: Circular coplanar orbital transfer and plane-change maneuvers using the Tsiolkovsky rocket equation.
- **Debris Ingestion & Cataloging**: CelesTrak and Space-Track TLE/OMM ingestion, spatial altitude filtering, SHA-256 caching.
- **Conjunction Screening Pipeline**: Coarse bounding-box filtering, Fine SGP4-propagated step evaluation, Golden-section numerical TCA refinement.
- **Multi-Objective Scoring & Ranking**: Normalization and weighted composite scoring combining delta-v propellant consumption and screened debris risk.
- **REST API & Job Worker**: Asynchronous background thread pool worker managing plan execution, progress states, and terminal results.
- **Handoff Artifacts**: Frozen REST API for Person 2 frontend integration (see [docs/FRONTEND_API_CONTRACT.md](docs/FRONTEND_API_CONTRACT.md)).

---

## Directory Structure

```text
D-DATO/
├── backend/
│   ├── app/
│   │   ├── api/v1/         # FastAPI frozen endpoints (health, plans, runs, heatmap, globe, validation, exports)
│   │   ├── core/           # Constants, config settings, logging
│   │   ├── data/           # Offline reference fixtures & loaders
│   │   ├── db/             # SQLAlchemy 2.x models & session factory
│   │   ├── schemas/        # Pydantic v2 validation contracts
│   │   ├── services/       # Astrodynamics, screening, pipeline, export, validation services
│   │   └── workers/        # Asynchronous worker manager & task runner
│   ├── scripts/            # Standalone demos & end-to-end smoke test
│   ├── tests/              # Unit & integration test suites
│   ├── requirements.txt    # Pinned Python package dependencies
│   ├── .env.example        # Environment configuration template
│   └── README.md
├── frontend/               # Person 2: React + TypeScript + Vite web interface
├── demo_data/              # Offline TLEs, catalogs, and test fixtures
├── docs/
│   ├── FRONTEND_API_CONTRACT.md # Frozen contract document for Person 2 frontend integration
│   ├── BACKEND_HANDOFF.md       # Final backend handoff and architecture summary
│   ├── ARCHITECTURE.md          # End-to-end backend architecture specifications
│   └── API.md                   # Detailed REST API specification
└── SPEC.md                 # Authoritative engineering specification
```

---

## Frontend Development (Person 2: Final Frontend Release, Phases P19–P24)

The web frontend is located in [`frontend/`](frontend/) and built using **React 19**, **TypeScript**, **Vite**, **Tailwind CSS**, **Plotly**, and **CesiumJS**.

### 1. Prerequisites & Location
- **Location**: `frontend/`
- **Node.js**: `v20+` (tested and benchmarked on **Node v24.14.1**)
- **npm**: `v10+` (tested on **npm v11.11.0**)
- **Backend Dependency**: Requires the Python FastAPI backend running concurrently on `http://127.0.0.1:8000`.

### 2. Environment Configuration
The API base URL is controlled via the `VITE_API_BASE_URL` environment variable:
```bash
# In frontend/
copy .env.example .env
```
Default setting:
```env
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Integrated Features (Complete P19–P24 Suite)
1. **Mission Planning Interface (P19)**: 6-section accessible orbital constraint form with live candidate grid estimation (capped at 300 candidates).
2. **Asynchronous Run Progress (P19)**: Real-time lifecycle polling across screening stages with stage progress bar and retry triggers.
3. **Screening Results Dashboard (P20)**: Authoritative summary metrics, ranked candidate tables with telemetry detail drawers, and close-approach event tables.
4. **2D Interactive Risk Heatmap (P21)**: Continuous Viridis color scale Plotly heatmap visualizing screening risk scores across deployment delays and altitudes, with inclination slice filtering.
5. **3D Interactive Orbit Globe (P22)**: CesiumJS 3D viewer rendering candidate tracks, debris trajectories, and conjunction encounters with explicit TEME-to-pseudo-fixed coordinate frame transformation.
6. **External Reference Validation Dashboard (P23)**: Benchmark comparison against external reference datasets (SOCRATES) with explicit data provenance badges, count cards, descriptive comparison metrics, and matched event cross-linking.
7. **Artifact Exports & Reporting (P24)**: Direct browser downloads of machine-readable multi-CSV ZIP packages and executive PDF screening reports generated by the backend.

### 4. Development Workflow
Start the frontend development server:
```bash
cd frontend
npm install
npm run dev
```
The application opens at [http://localhost:5173](http://localhost:5173).

### 5. Running Frontend Tests, Lint, and Build
```bash
cd frontend

# Run full Vitest test suites (121 tests across 28 suites)
npm test

# Run strict linter (0 errors, 0 warnings)
npm run lint

# Production bundle build
npm run build
```


