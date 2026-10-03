# D-DATO System Specification (Person 1 Backend)

## 1. System Mission & Scope
The Debris-Aware Orbit & Deployment-Window Planner (D-DATO) computes optimal, collision-screened deployment windows and orbital insertion parameters for Low Earth Orbit (LEO) satellites. Person 1 is exclusively responsible for the computational engine, data ingestion, database layer, background screening jobs, and REST API.

## 2. System Architecture & Pipeline Stages

```text
[Mission Plan Input] ──> [Candidate Generator] ──> [Fuel / Delta-V Estimator]
                                                            │
[Debris TLE Ingestion] ──> [SGP4 Propagator] ───────────────┼──> [Broad-phase Filter]
                                                            │
                                                            └──> [Narrow-phase TCA Refinement]
                                                                        │
                                                                        v
[Ranked Recommendations] <── [Multi-Objective Ranking] <── [Risk Scoring Engine]
```

### Stage 1: Candidate Generation
- Discretizes the target deployment epoch window into time slices.
- Generates candidate orbital injection states based on target semi-major axis, eccentricity, inclination, RAAN, and argument of perigee.

### Stage 2: Fuel / Delta-V Budgeting
- Calculates transfer maneuvers from launch vehicle drop-off orbit to target orbit.
- Evaluates plane changes and phasing maneuvers.
- Computes propellant consumption using the Tsiolkovsky rocket equation.

### Stage 3: Debris Ingestion & SGP4 Ephemeris Propagation
- Ingests active and inactive debris TLEs from CelesTrak / Space-Track or offline demo fixtures.
- Filters debris objects using coarse orbital regime bounding (altitude, inclination envelope).
- Propagates satellite candidate states and debris objects over the screening horizon using the SGP4 algorithm.

### Stage 4: Conjunction Screening & TCA Refinement
- Performs broad-phase spatial distance screening using radial/along-track/cross-track tolerance bounding.
- Refines candidates passing broad-phase screening using numerical minimization (Brent's method / golden section) to isolate Time of Closest Approach (TCA) and minimum miss distance.

### Stage 5: Screening Risk Scoring
- Computes composite risk metric incorporating miss distance, relative velocity at TCA, and positional covariance approximation.

### Stage 6: Multi-Objective Candidate Ranking
- Evaluates candidate orbits using a Pareto / weighted multi-objective scoring formula balancing:
  - Debris conjunction risk
  - Delta-V / fuel consumption
  - Launch/deployment window alignment and duration

## 3. Data Entities
- **MissionPlan**: Target orbit specifications, payload mass, propulsion Isp, launch window bounds.
- **ScreeningRun**: Execution instance linked to a MissionPlan, capturing execution status, parameters, and timestamps.
- **CandidateOrbit**: Discrete candidate deployment window and orbital insertion state.
- **ConjunctionEvent**: Close-approach event between candidate orbit and debris object (TCA, miss distance, relative velocity).
- **DebrisObject**: Cataloged space debris or active satellite with TLE metadata.

## 4. API Endpoints
All API endpoints follow RESTful conventions under `/api/v1`:
- `/health`: Service liveness and readiness probes.
- `/plans`: Mission plan CRUD.
- `/runs`: Screening run lifecycle and execution triggering.
- `/runs/{id}/candidates`: Ranked candidate deployment windows.
- `/runs/{id}/events`: Conjunction event log.
- `/runs/{id}/heatmap`: Risk heatmap matrix data for UI visualization.
- `/runs/{id}/globe`: 3D orbit trajectory and encounter markers.
- `/validation/plan`: Input validation and constraint sanity checks.
- `/runs/{id}/export/csv`: Tabular export of candidates and conjunctions.
- `/runs/{id}/export/pdf`: Formatted executive summary report.
