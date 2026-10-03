# D-DATO Backend Service (Phase P0–P18 Hardened & Frozen)

D-DATO (Debris-Aware Orbit & Deployment-Window Planner) FastAPI Backend Foundation.

This package provides the authoritative astrodynamics constants, unit and time conventions, centralized configuration system, normalized SQLAlchemy 2.x persistence layer, background execution workers, REST APIs, and automated test suite.

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
> All candidate evaluations, close-approach screenings, risk scoring metrics, and external reference comparisons represent decision-support screening evidence only.

---

## Backend Quick Start

This guide uses standard Windows PowerShell commands for the verified development environment.

### 1. Prerequisites
- **Python**: Version 3.10+ (tested and verified on **Python 3.13.15 64-bit**)
- **Operating System**: Windows (PowerShell or Command Prompt)

### 2. Virtual Environment Setup
From the `backend/` directory:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
Install verified dependencies (including exact ReportLab version `reportlab==5.0.1`):
```powershell
pip install -r requirements.txt
python -m pip check
```

### 4. Environment Configuration
Copy `.env.example`:
```powershell
copy .env.example .env
```
Default settings work out-of-the-box without requiring changes:
- `DEMO_MODE=true`
- `DATABASE_URL=sqlite:///./d_dato.db`
- `SOCRATES_ENABLED=false` (offline demo fixture used by default)

### 5. Start the FastAPI Development Server
```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Interactive docs:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health**: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### 6. Run Automated Tests
```powershell
# Full test suite (quiet)
.\venv\Scripts\pytest.exe -q

# Unit tests only
.\venv\Scripts\pytest.exe tests\unit -q

# Integration tests only
.\venv\Scripts\pytest.exe tests\integration -q
```

### 7. Run End-to-End Smoke Test
Verify the complete frozen API surface offline with network blocking:
```powershell
python scripts\smoke_test_backend.py
```

### 8. Run Standalone Demos
Each demo exercises a specific component offline with zero network connectivity:
- `python scripts\demo_p13_api.py` (REST API lifecycle demo)
- `python scripts\demo_p14_heatmap.py` (2D risk density matrix demo)
- `python scripts\demo_p15_globe.py` (3D TEME-frame globe trajectories demo)
- `python scripts\demo_p16_validation.py` (External reference validation comparison demo)
- `python scripts\demo_p17_exports.py` (CSV ZIP & PDF report generation demo)

All demos execute cleanly and remove temporary files upon completion.
