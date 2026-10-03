# D-DATO Backend Architecture

## Overview
The D-DATO backend is structured as a decoupled, layered Python service combining high-performance numerical astrodynamics algorithms with an asynchronous REST API and worker execution model.

```text
┌────────────────────────────────────────────────────────┐
│                   FastAPI Interface                    │
│            (app/api/v1 - Routing & Controllers)        │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    Service Layer                       │
│    (Screening, Ingestion, Ranking, Heatmap, Export)    │
└─────────────┬───────────────────────────┬──────────────┘
              │                           │
┌─────────────▼─────────────┐ ┌───────────▼──────────────┐
│   Core Astrodynamics      │ │      Data & Database     │
│   (app/core)              │ │      (app/db, app/data)  │
│  - Candidate Generator    │ │  - SQLAlchemy Repos      │
│  - SGP4 Propagation       │ │  - CelesTrak Ingestion   │
│  - Conjunction & TCA      │ │  - TLE Cache & Parser    │
│  - Fuel & Delta-V         │ │  - Demo Catalog Loader   │
│  - Multi-Objective Ranker │ │                          │
└───────────────────────────┘ └──────────────────────────┘
```

## Subsystems

1. **`app/api`**: FastAPI HTTP routes, request validation, serialization, error handlers.
2. **`app/core`**: Pure Python numerical astrodynamics algorithms, physical constants, and central configuration. Completely decoupled from HTTP frameworks.
3. **`app/services`**: Business logic orchestration connecting database models, core algorithms, and external data sources.
4. **`app/workers`**: Background job execution for screening pipelines that may take seconds to minutes.
5. **`app/data`**: Data ingestion adapters for CelesTrak and Space-Track, TLE file parsing, local caching, and offline demo data loading.
6. **`app/db`**: Database engine configuration, SQLAlchemy 2.x ORM models, and CRUD repositories.
7. **`app/schemas`**: Pydantic models for request bodies, responses, and internal data transfer objects.
8. **`app/utils`**: Reusable units, time conversions (UTC, JD, GMST), and structured logging.

---

## Database Architecture (Phase P3)

### 1. Engine & Compatibility
- **Default Database**: Local SQLite (`sqlite:///./d_dato.db`) configured with `check_same_thread=False` for development.
- **Production Compatibility**: The schema design and query syntax in the repository layer are strictly standard SQL / SQLAlchemy 2.x, enabling drop-in migration to PostgreSQL (`postgresql+psycopg2://...`) without repository rewrites.
- **Isolated Testing**: Unit tests use in-memory SQLite engines (`sqlite:///:memory:`) to ensure no side effects on development database files.

### 2. ORM vs. Pydantic Separation
- **SQLAlchemy Models (`app.db.models`)**: Represent normalized relational tables and database persistence structures.
- **Pydantic Schemas (`app.schemas`)**: Represent API request contracts, serialization boundaries, and domain validation.
- Domain and API code never manipulate ORM session internals directly; interactions are channeled through repository abstractions.

### 3. Core Database Entities
- **`Plan` (`plans`)**: Mission planning envelope defining altitude/inclination search grids, deployment delays, mass, Isp, and multi-objective ranking weights.
- **`Run` (`runs`)**: Asynchronous execution lifecycle tracking (statuses: `queued`, `running`, `completed`, `failed`, `cancelled`), progress percentage, and stage logging.
- **`Candidate` (`candidates`)**: Evaluated deployment candidates with calculated delta-v, propellant mass, fuel fraction, composite risk score, and assigned rank.
- **`DebrisObject` (`debris_objects`)**: Tracked space debris and active satellite catalog entries preserving raw verbatim TLE lines and provenance metadata.
- **`DataSnapshot` (`data_snapshots`)**: Ingestion provenance record tracking catalog fetch timestamps, data age in seconds, and cached object counts.
- **`ConjunctionEvent` (`conjunction_events`)**: Close-approach encounters linking candidates to catalog debris objects with TCA, miss distance, relative velocity, and threshold.
- **`ValidationRecord` (`validation_records`)**: Benchmark comparisons against external screening sources (such as SOCRATES).

### 4. Entity Relationships
```text
Plan (1) ──< Run (N)
              ├──< Candidate (N) ──< ConjunctionEvent (N) >── DebrisObject (1)
              ├──< ConjunctionEvent (N)
              └──< ValidationRecord (N)
```

### 5. Transaction & Session Policy
- Sessions are request/job-scoped (`get_db()` dependency in FastAPI or scoped contexts in workers).
- Repositories enforce explicit transaction boundaries: commits and rollbacks are isolated within repository operations or caller-managed transactions. Global long-lived sessions are forbidden.

### 6. Timestamp Policy
- **UTC Everywhere**: All timestamps in the database use UTC.
- **TypeDecorator Enforcement**: All datetime columns use a custom `UTCDateTime` TypeDecorator that:
  - Strictly rejects naive datetimes on insert/update with `ValueError`.
  - Automatically restores `tzinfo=timezone.utc` upon loading from database engines that strip timezone metadata (such as SQLite).

---

## Data Ingestion Architecture (Phase P4)

### 1. Ingestion Pipeline Flow
The catalog ingestion pipeline operates as a unidirectional, fault-tolerant processing flow:

```text
External Source (CelesTrak / Demo)
              │
              ▼
    [ CelesTrak Client ] ──(Rate Limit & Freshness Check)──▶ [ Filesystem Cache ]
              │                                                     │
              └───────────────────┬─────────────────────────────────┘
                                  ▼
                         [ Catalog Parsers ]
                     (TLE, OMM JSON, OMM CSV)
                                  │
                                  ▼
                     [ CanonicalElementRecord ]
                       (6-digit ID compatible)
                                  │
                                  ▼
                      [ Filtering Pipeline ]
                (Validity, Altitude, Inclination,
                 Categorization, Deduplication)
                                  │
                                  ▼
                    [ Database Persistence Layer ]
                   (Idempotent Bulk Upsert to DB,
                     DataSnapshot Metadata Audit)
```

### 2. Operational Ingestion Modes
The system operates across three explicit modes (`IngestionMode`):
- **`live`**: Data fetched directly from external remote APIs (e.g. CelesTrak GP endpoint) when eligible under the rate-limiting policy.
- **`cache`**: Data retrieved from the local filesystem raw cache when the cache is fresh (< 2 hours old) or when external networks are unreachable.
- **`demo`**: Data loaded from bundled offline fixtures (`demo_data/`) when no remote network or cache is available, or when explicit offline demo mode is activated.

### 3. Raw Filesystem Cache vs. Database `DataSnapshot`
To decouple bulk raw payloads from relational databases:
- **Filesystem Cache (`demo_data/cache/celestrak/<key>/`)**: Stores raw downloaded payload bytes (`payload.json`, `payload.tle`, `payload.csv`) alongside `metadata.json` (SHA-256 hash, fetch timestamp, byte count, object count, format).
- **`DataSnapshot` Entity (`data_snapshots`)**: Tracks operational metadata in the relational database: snapshot UUID, catalog source, fetch timestamp, calculated `data_age_seconds`, ingested object counts, cache key reference, outcome status, and diagnostic notes.

### 4. Idempotent Ingestion & Deduplication
- **Deduplication Identity**: Records are uniquely identified by the 4-tuple: `(source, catalog_id, epoch, element_format)`.
- **Database Idempotence**: Ingestion operations converge to a single current record for each `(norad_id, source)` pair in `debris_objects`. Re-ingesting an updated catalog refreshes orbital parameters and timestamps without creating duplicate rows or deleting historical `DataSnapshot` audit records.

### 5. Source Provenance
Every ingested record preserves:
- Original catalog source (`celestrak`, `demo`, `spacetrack`)
- Format identifier (`tle` or `omm`)
- Timezone-aware fetch timestamp (`fetched_at`)
- Data age in seconds (`data_age_seconds = (now_utc - fetched_at).total_seconds()`)
- Verbatim raw lines (`tle_line1`, `tle_line2`) or full serialized source payload (`raw_source_payload`)

---

## Orbital Propagation Architecture (Phase P5)

D-DATO decouples catalog debris propagation from analytical candidate orbit propagation. Both streams yield unified, immutable `StateVector` instances in the TEME reference frame:

```text
Catalog Debris / Objects                  Candidate Mission Envelope
            │                                         │
            ▼                                         ▼
 CanonicalElementRecord                      Candidate Orbit Parameters
 (From Ingestion Service)                    (alt, inc, raan, u0, epoch)
            │                                         │
            ▼                                         ▼
      SGP4 Adapter                             CircularJ2Orbit
(Sgp4Propagator / Satrec)                 (Analytical J2 Secular Model)
            │                                         │
            ▼                                         ▼
     TEME StateVector                          TEME StateVector
(r in km, v in km/s, TEME)                (r in km, v in km/s, TEME)
            │                                         │
            └────────────────────┬────────────────────┘
                                 ▼
              [ Future Conjunction Screening (P6) ]
```

### Key Architectural Boundaries
1. **Model Independence**: Neither `app.core.orbit` nor `app.core.propagation` depend on FastAPI, SQLAlchemy, or external network services.
2. **Canonical StateVector**: All propagation methods return frozen `StateVector` instances containing position $(x, y, z)$ in $\text{km}$, velocity $(v_x, v_y, v_z)$ in $\text{km/s}$, timezone-aware UTC `timestamp`, `frame="TEME"`, and model identifier (`"SGP4"` or `"CircularJ2"`).
3. **Identifier Integrity**: SGP4 Alpha-5 satellite number constraints are handled via an internal numerical surrogate without leaking to or mutating the canonical object identifier.

---

## Candidate Generation Architecture (Phase P6)

D-DATO candidate generation discretizes the mission planning search envelope into pure, deterministic candidate deployment configurations:

```text
Plan / Configuration
       │
       ├── altitude grid
       ├── inclination grid
       └── delay grid
              │
              ▼
       Candidate Generator
              │
              ▼
       CandidateOrbit list
              │
       ┌──────┴────────┐
       ▼               ▼
future fuel       future screening
```

### Architectural Properties
1. **Zero Database / HTTP Coupling**: The candidate generator (`app.core.candidate_generator`) is pure Python without database sessions, SQL queries, or remote network calls.
2. **Pure Domain Model**: Candidate configurations are represented as frozen `CandidateOrbit` dataclasses, decoupled from SQLAlchemy ORM models.
3. **Cartesian Product**: Formed strictly from $\text{altitude} \times \text{inclination} \times \text{deployment delay}$. RAAN is derived via the configured coupling constant ($0.25068^\circ/\text{min}$) rather than an independent search dimension.
4. **Guarded Ceiling**: Strictly rejects requests exceeding `MAX_CANDIDATES = 300` with `CandidateGenerationError` without silent truncation.
5. **Deterministic Ordering & Identity**: Ordered ascendingly by altitude $\rightarrow$ inclination $\rightarrow$ delay, with deterministic `ALT{alt}_INC{inc}_DELAY{delay}` identifier encoding.

---

## Delta-V and Fuel Estimation Architecture (Phase P7)

D-DATO evaluates early-stage conservative maneuver and propellant requirements for each candidate orbit option:

```text
CandidateOrbit
      │
      ▼
Delta-V Estimator
      │
      ├── Hohmann transfer
      ├── plane change
      └── Tsiolkovsky
      │
      ▼
DeltaVEstimate
      │
      ├── delta_v_m_s
      ├── propellant_mass_kg
      ├── fuel_fraction
      └── within_dv_budget
```

### Future Phase Multi-Objective Integration
In downstream phases, delta-v estimates will be coupled with conjunction screening results:

```text
DeltaVEstimate
      +
Conjunction results
      ↓
risk score
      ↓
multi-objective ranking
```
*(Conjunction screening, risk evaluation, and composite ranking are not executed during Phase P7).*

### Architectural Properties
1. **Decoupled Domain Result**: `DeltaVEstimate` is a frozen dataclass independent of `CandidateOrbit` and SQLAlchemy ORM models.
2. **Conservative Scalar Summation**: Plane-change and altitude-transfer impulses are evaluated at reference speed and summed as scalars without vector combination or continuous burn losses.
3. **Pure Closed-Form Execution**: Fully analytic without numerical ODE integrators, database queries, or network I/O.

---

## Conjunction Screening & TCA Refinement Architecture (Phase P8)

D-DATO implements a two-pass physical conjunction screening architecture that screens candidate deployment options against space debris catalogs:

```text
CandidateOrbit
      │
      ▼
Circular J2 propagation
      │
      ├───────────────┐
      │               │
      │          same UTC t
      │               │
      ▼               ▼
Candidate State    Debris State
                       │
                     SGP4
                       │
      └───────────────┘
               │
               ▼
        Relative Position
               │
               ▼
        30-sec coarse scan
               │
               ▼
          local minima
               │
               ▼
      bounded TCA refinement
               │
               ▼
       events <= 25 km
               │
               ▼
          deduplication
               │
               ▼
      ConjunctionEvent results
```

### Architectural Properties
1. **Two-Pass Separation**:
   - **Pass 1 (Coarse Scan)**: 30-second time steps with 260 km threshold and local minima detection.
   - **Pass 2 (TCA Refinement)**: Bounded 1-D numerical scalar minimization via SciPy (`minimize_scalar`, bounded method) with $\le 0.01\text{ s}$ convergence tolerance.
2. **Strict Retention Threshold**:
   - Only events with refined miss distance $\le 25.0\text{ km}$ (`SCREENING_EVENT_THRESHOLD_KM`) are retained.
   - Threshold recorded in database is $25.0\text{ km}$; the 260 km threshold is purely internal to coarse candidate detection.
3. **Physical Screening Only**:
   - Computes physical miss distance (km) and relative velocity magnitude (km/s).
   - Does **NOT** compute collision probabilities, probability of impact, severity grades, or risk scores.
4. **Time Chunking & Memory Safety**:
   - Screened in 1-hour time chunks (`SCREENING_TIME_CHUNK_SECONDS = 3600`) to bound array allocations.
   - Capped at `SCREENING_MAX_EVENTS_PER_CANDIDATE = 1000` to prevent memory blow-up on pathological scenarios.
5. **Deterministic Deduplication & Ordering**:
   - Merges detections for the same candidate/debris pair within 30 seconds, retaining minimum miss distance.
   - Deterministically ordered: Candidate ID $\rightarrow$ TCA $\rightarrow$ Miss Distance $\rightarrow$ Debris NORAD ID.
6. **Error Isolation**:
   - SGP4 failure for a single debris object logs a diagnostic warning, skips that object, and continues screening remaining objects.

---

## Risk Assessment Architecture (Phase P9)

Phase P9 converts P8 conjunction screening events and catalog metadata into a bounded, explainable screening score:

```text
ConjunctionEvent results
        │
        ▼
   Risk Assessor
        │
        ├── minimum miss distance
        ├── accepted event count
        ├── relative velocity summary
        └── data-age metadata
        │
        ▼
   RiskAssessment
        │
        └── bounded 0–100 screening score
```

### Architectural Boundaries
1. **Pure Functional Core**:
   - `backend/app/core/risk.py` operates purely on domain objects, numbers, and strings.
   - Contains zero database imports, zero FastAPI imports, and zero network I/O.
2. **Screening Index vs. Probability**:
   - D-DATO risk is an early-stage screening index bounded strictly in $[0, 100]$.
   - It is not a collision probability ($P_c$), probability of impact, or operational flight-safety determination.
3. **Explainable Component Breakdown**:
   - Returns full component transparency (`proximity_score`, `event_count_score`, `accepted_event_count`, `minimum_miss_distance_km`, `minimum_relative_velocity_km_s`, `maximum_relative_velocity_km_s`, `uncertainty_level`, `uncertainty_notes`).

---

## Candidate Ranking Architecture (Phase P10)

Phase P10 ranks candidate deployment options using normalized fuel consumption and close-approach screening risk:

```text
P6 CandidateOrbit
       │
       ├───────────────┐
       ▼               ▼
P7 Fuel Estimate    P9 Risk Assessment
       │               │
       └───────┬───────┘
               ▼
         Ranking Engine
               │
       ┌───────┼────────┐
       ▼       ▼        ▼
     fuel     risk   weights
       │       │        │
       └───────┴────────┘
               │
               ▼
        RankedCandidate
               │
               ▼
             rank
```

### Architectural Properties
1. **Zero Re-Screening**:
   - Ranking does **NOT** invoke P8 conjunction screening, SGP4 propagation, or numerical TCA refinement.
   - P10 consumes precomputed `DeltaVEstimate` and `RiskAssessment` records.
2. **Deterministic Post-Processing**:
   - Sorting uses a 4-tier deterministic key: composite score descending $\rightarrow$ risk score ascending $\rightarrow$ delta-v ascending $\rightarrow$ candidate ID ascending.
   - Ranks are contiguous integers $1, \dots, N$.
3. **Decoupled Persistence**:
   - Pure functional domain engine in `backend/app/core/ranking.py`.
   - Optional persistence updates `Candidate.rank` via atomic repository operations (`CandidateRepository.bulk_update_ranks`).

---

## End-to-End Planning Pipeline (Phase P11)

Phase P11 connects the independent scientific components into an end-to-end synchronous orchestration pipeline (`backend/app/services/pipeline_service.py`):

```text
Plan
 │
 ▼
Ingestion
 │
 ▼
Canonical catalog
 │
 ▼
Candidate Generator
 │
 ▼
195-or-fewer CandidateOrbit objects
 │
 ├───────────────┐
 ▼               ▼
P7 Fuel         P8 Screening
 │               │
 │               ▼
 │             P9 Risk
 │               │
 └───────┬───────┘
         ▼
      P10 Rank
         │
         ▼
   Persistence
         │
         ▼
    PipelineResult
```

### Architectural Properties & Execution Boundaries
1. **Orchestration Only**:
   - `PipelineService` orchestrates execution order and data flow without duplicating or modifying any astrodynamic formulas, propagation loops, TCA refinements, or ranking equations.
   - Core scientific engines remain pure, decoupled domain modules (`candidate_generator.py`, `fuel.py`, `conjunction.py`, `risk.py`, `ranking.py`).
2. **Synchronous Execution Core**:
   - Phase P11 executes synchronously to serve as the reliable computational engine.
   - Phase P12 will subsequently wrap this synchronous engine in an asynchronous worker lifecycle.
3. **Deterministic Progress & Run Lifecycle**:
   - Tracks coarse stages: `ingestion` (0→15%), `candidate_generation` (15→25%), `fuel_estimation` (25→35%), `conjunction_screening` (35→75%), `risk_assessment` (75→85%), `ranking` (85→95%), `persistence` (95→99%), `completed` (100%).
   - Failures transition `Run.status` to `failed`, preserve error diagnostics in `error_message`, and set `current_stage = "failed"`.
4. **Controlled Transaction Boundaries**:
   - Network I/O and heavy scientific computations do not hold open database transactions.
   - Persistence occurs in a dedicated transaction boundary via repository bulk operations (`CandidateRepository.bulk_create`, `ConjunctionEventRepository.bulk_create`).
5. **Full Provenance & Run Isolation**:
   - Every execution operates under an independent `Run.id`. Repeated runs of the same plan produce distinct candidate and event records without overwriting historical run provenance.

---

## Async Run Lifecycle (Phase P12)

Phase P12 provides non-blocking asynchronous execution and lifecycle management for D-DATO screening runs (`backend/app/services/run_service.py` and `backend/app/workers/screening_worker.py`):

```text
Client / Future API
        │
        ▼
    RunService
        │
        ├── create Plan
        ├── create Run (queued)
        └── submit run_id
                │
                ▼
         WorkerManager
                │
                ▼
         Worker Thread
                │
                ▼
          P11 Pipeline
                │
                ▼
        completed / failed
```

### Architectural Properties & Execution Boundaries
1. **Separation of Execution Layers**:
   - The scientific pipeline (`P11 PipelineService`) remains purely synchronous.
   - `RunService` and `WorkerManager` manage thread dispatching, lifecycle state transitions, duplicate submission protection, and polling status summaries.
2. **In-Process Worker Architecture**:
   - Implemented using Python's standard-library `concurrent.futures.ThreadPoolExecutor`.
   - Default concurrency is `WORKER_MAX_CONCURRENCY = 1` to match CPU-intensive SGP4 screening and SQLite transactional single-writer properties.
   - Reusable worker manager instance with clean, graceful shutdown (`executor.shutdown(wait=True)`).
3. **Database as the Authoritative Source of Truth**:
   - In-process `Future` objects are process-local tracking mechanisms only.
   - The SQLAlchemy database `Run.status` is the authoritative lifecycle state across restarts.
4. **Thread & Session Safety**:
   - Sessions are never passed across threads. Each worker execution thread opens a fresh, dedicated database session from `SessionLocal` and closes it on termination.
5. **In-Process Limitation**:
   - Suitable for local development, hackathon demonstrations, and single-process deployments.
   - Not a distributed or durable job queue. If the process terminates abruptly, in-memory `Future` references are lost; database records remain in their last persisted status.
6. **Cancellation Semantics**:
   - The `cancelled` status is reserved in the lifecycle state machine for future development. Active runtime thread cancellation is intentionally deferred.

---

## FastAPI REST API Architecture (Phase P13)

### 1. Layered Component Architecture

```text
React frontend (future)
        │
        ▼
     FastAPI
        │
   ┌────┼─────────┐
   ▼    ▼         ▼
 Plans Runs    Results (Candidates & Events)
   │    │         │
   └────┼─────────┘
        ▼
    RunService
        │
        ▼
    P12 Worker
        │
        ▼
   P11 Pipeline
```

### 2. Architectural Boundaries & Principles
1. **Thin Controller Pattern**:
   - FastAPI route handlers in `app/api/v1/` contain no business logic, no SQL queries, and no astrodynamics or scientific computations.
   - Routes act purely as HTTP protocol translators: validating request models, delegating to `RunService` and repositories, and serializing to Pydantic responses.
2. **Service Layer Ownership**:
   - `RunService` owns the lifecycle workflow: validating plan envelopes, persisting records, submitting jobs to `WorkerManager`, tracking thread progress, and assembling paginated result responses.
3. **Asynchronous Non-Blocking Ingress**:
   - `POST /api/v1/plans` creates the plan, initializes the run, and asynchronously submits it to the background worker. It returns `HTTP 202 Accepted` immediately without blocking for pipeline execution.
4. **Strictly Read-Only Result Endpoints**:
   - `GET /runs/{run_id}`, `GET /runs/{run_id}/candidates`, and `GET /runs/{run_id}/events` query persisted database records only. They do not trigger re-screening, re-ranking, or recalculation.
   - If a run is still executing, candidate and event endpoints return `HTTP 200 OK` with `total: 0` and empty items lists.
5. **Database-Level Pagination**:
   - Candidate and conjunction event endpoints enforce database-level `OFFSET`, `LIMIT`, and deterministic `ORDER BY` queries via SQLAlchemy repository methods, ensuring efficient retrieval without loading entire result tables into Python memory.
6. **Strict Schema Separation**:
   - SQLAlchemy ORM models (`app.db.models`) remain completely decoupled from public API schemas (`app.schemas`).
   - Pydantic v2 `ConfigDict(from_attributes=True)` is used for data transfer object transformations.

---

## 2D Risk Heatmap Service Architecture (Phase P14)

### 1. Data Flow Architecture

```text
Persisted Candidate results
        │
        ▼
   HeatmapService
        │
        ▼
GET /api/v1/runs/{run_id}/heatmap
        │
        ▼
Future React + Plotly frontend
```

### 2. Architectural Boundaries & Principles
1. **Consumption of Persisted Results Only**:
   - `HeatmapService` and `GET /api/v1/runs/{run_id}/heatmap` consume already-persisted candidate results and conjunction event records.
   - The service does NOT recompute risk scores, rerun screening, regenerate orbits, re-rank candidates, or execute orbital propagations.
2. **Deterministic Multi-Layer 2D Grid**:
   - The coordinate grid is defined by:
     - **X axis**: `delay_minutes` (deployment delay in minutes)
     - **Y axis**: `altitude_km` (circular orbit altitude in km)
     - **Slice dimension**: `inclination_deg` (each distinct inclination produces one 2D layer)
   - Matrix shape: `len(altitude_values_km)` rows by `len(delay_values_minutes)` columns.
   - Values mapping: `values[row][column]` corresponds exactly to `altitude_values_km[row]` and `delay_values_minutes[column]`.
3. **Null-Cell Representation**:
   - If a candidate coordinate is missing from the persisted result set, that grid position in `values[row][col]` is represented as `null` (`None`).
   - The service strictly avoids interpolation or fabrication of missing grid points.
4. **Single-Query Read Optimization**:
   - Candidate options are retrieved using `CandidateRepository.list_by_run_for_heatmap` sorted deterministically by `inclination_deg ASC`, `altitude_km ASC`, `deployment_delay_minutes ASC`.
   - Conjunction event statistics (`accepted_event_count`, `minimum_miss_distance_km`) are retrieved using a single aggregate query grouped by `candidate_id`, avoiding N+1 database roundtrips.
5. **Non-Blocking Run State Compatibility**:
   - If a run is currently `queued` or `running` and candidates have not yet been persisted, the service returns `HTTP 200 OK` with `layers = []`, `total_candidates = 0`, and `populated_cells = 0` without blocking waiting for worker completion.
6. **Strictly Read-Only & Offline**:
   - The endpoint makes zero external network calls, ensuring deterministic offline performance in demonstration and production environments.

---

## 3D Globe Trajectory Service Architecture (Phase P15)

### 1. Data Flow Architecture

```text
Persisted Run, Plan, Candidates & Debris
                  │
                  ▼
            GlobeService
       ┌──────────┴──────────┐
       ▼                     ▼
Circular J2 SVS        SGP4 Debris SVS
 (candidates)             (debris)
       │                     │
       └──────────┬──────────┘
                  ▼
       SGP4 at TCA for Events
                  │
                  ▼
    GET /api/v1/runs/{run_id}/globe
                  │
                  ▼
     Future Cesium/React Frontend
```

### 2. Architectural Boundaries & Principles
1. **Coordinate Frame & Physics Contract**:
   - Coordinate Frame: `TEME` (True Equator Mean Equinox). Positions in `km`, velocities in `km/s`, time scale in `UTC` (ISO 8601).
   - Trajectory state vectors are never labeled ECEF.
2. **Per-Candidate Deployment Epoch Semantics**:
   - Each candidate orbit begins propagation strictly at its `deployment_epoch` (`plan.epoch_start + deployment_delay_minutes`).
   - No candidate samples are generated backwards or prior to deployment.
   - Trajectory samples span `[deployment_epoch, deployment_epoch + screening_days]`.
   - Propagated using `CircularJ2` model via `propagate_circular_j2_many`.
3. **Debris Ingestion & SGP4 Propagation**:
   - Debris orbits are sampled across the mission screening window `[plan.epoch_start, plan.epoch_start + screening_days]`.
   - Propagated using `Sgp4Propagator` from existing canonical TLE records.
4. **Deterministic Debris Priority & Fallback**:
   - Debris participating in conjunction events for the selected candidate set are given first priority.
   - Remaining slots up to `max_debris` are filled deterministically ordered by `norad_id ASC, id ASC`.
   - Fallback queries strictly avoid non-deterministic `LIMIT` without `ORDER BY`.
5. **Event Selection Consistency & Cartesian Position**:
   - Conjunction event markers are strictly filtered to the selected candidates and included debris objects.
   - Event marker positions (`x_km`, `y_km`, `z_km`) are evaluated by propagating the threatening debris object using `Sgp4Propagator` at the exact persisted `tca`.
   - Positions are never approximated or substituted with miss distance vectors.
6. **Explicit Candidate Selection**:
   - Supports optional `candidate_ids` query parameter (comma-separated string).
   - If provided, returns only the requested candidates in requested order; raises `404 CANDIDATE_NOT_FOUND` if any requested ID does not belong to the run; raises `422 INVALID_CANDIDATE_IDS` for malformed/empty IDs.
   - If omitted, defaults to top-ranked candidates up to `max_candidates`.
7. **Strictly Read-Only & Offline**:
   - Does not submit background jobs, execute pipelines, fetch fresh TLEs, or make network calls.
   - Queued or running runs with no persisted results return `200 OK` with empty track lists.

---

## External Conjunction Validation Architecture (Phase P16)

### 1. Data Flow Architecture

```text
Persisted D-DATO Events
        │
        ├──── Validation Source Adapter (SocratesAdapter)
        │
        ├──── Cache / Demo Fixture (FileSystemCache / socrates_fixture.json)
        │
        ▼
ValidationService
        │
        ▼
Persisted ValidationRecord
        │
        ▼
Validation REST API
  (POST /api/v1/runs/{run_id}/validation)
  (GET  /api/v1/runs/{run_id}/validation)
  (GET  /api/v1/validations/{validation_id})
```

### 2. Scientific & Architectural Positioning

1. **Non-Operational Validation Positioning**:
   - SOCRATES is an external validation/reference source providing comparative benchmark evidence.
   - D-DATO conjunction screening remains entirely independent and is the primary screening output.
   - Validation does **NOT** replace conjunction screening.
   - Validation does **NOT** produce or claim true collision probability.
   - It does not represent certified flight safety, operational conjunction assessment, CDM generation, maneuver recommendations, or launch COLA.

2. **Screening Isolation & Read-Only Invariance**:
   - Validation operates strictly on already-persisted `ConjunctionEvent` records.
   - Screening algorithms (Phase P8), risk assessments (Phase P9), and candidate rankings (Phase P10) are **NEVER rerun** during validation.

3. **Transparent Matching Hierarchy**:
   - Matches are formed using deterministic, configurable criteria:
     - Exact canonical debris NORAD identifier agreement.
     - TCA absolute difference $\le$ `tca_tolerance_seconds` (default: 300.0s).
     - Miss-distance absolute difference $\le$ `miss_distance_tolerance_km` (default: 5.0km, where external miss distance is available).
   - Assignment is strictly 1-to-1 greedy, ordered by smallest absolute TCA error, then smallest absolute miss distance error.
   - Match criteria are recorded explicitly on each paired match (e.g. `['debris_norad_id', 'tca_tolerance', 'miss_distance_tolerance']` or `['debris_norad_id', 'tca_tolerance', 'miss_distance_unavailable']`).

4. **Provenance & Offline-First Strategy**:
   - Live external SOCRATES integration is disabled by default (`SOCRATES_ENABLED=False`).
   - When disabled or offline, reference data falls back to local filesystem cache (`demo_data/cache/socrates/`).
   - When cache is absent in demo mode, deterministic bundled fixture data (`demo_data/validation/socrates_fixture.json`) is loaded with zero network access.
   - Provenance is explicitly tagged on all records and responses:
     - `"socrates_live"`: live remote network fetch.
     - `"socrates_cache"`: cached raw payload.
     - `"socrates_demo_fixture"`: bundled deterministic synthetic fixture.

---

## CSV & PDF Export Architecture (Phase P17)

### 1. Data Flow Architecture

```text
Persisted Plan / Run / Candidate / Event / Validation
                         |
                         v
                   ExportService
                    /         \
                   /           \
                  v             v
               CSV ZIP         PDF
                  \             /
                   \           /
                    v         v
                  REST download
                         |
                         v
                  Future frontend
```

### 2. Architectural Principles & Guarantees

1. **Exports Use Strictly Persisted Data**:
   - The export layer operates exclusively over previously persisted database entities (`Plan`, `Run`, `Candidate`, `ConjunctionEvent`, `ValidationRecord`).
   - Source-of-truth database records are treated as immutable during export serialization.

2. **No Science Recalculation**:
   - The ExportService **never** recomputes candidate orbits, delta-v estimates, propellant fractions, SGP4 propagations, conjunction encounters, risk assessments, or candidate rankings.
   - All physical parameters and ranking indicators are formatted and emitted verbatim.

3. **No Worker Submission or Pipeline Execution**:
   - Export endpoints are synchronous, low-latency, read-only GET requests (`/api/v1/runs/{run_id}/exports/csv` and `/api/v1/runs/{run_id}/exports/pdf`).
   - No tasks are submitted to `WorkerManager`, and `PipelineService.run_pipeline` is never triggered.

4. **Zero External Network Dependencies**:
   - Neither the CSV builder nor the PDF engine performs remote HTTP calls, external image fetches, or third-party catalog lookups.
   - Generation executes completely offline.

5. **No Frontend Dependency for PDF Generation**:
   - Reports are generated completely headlessly within the backend runtime using ReportLab.
   - No headless browser, Node.js, Puppeteer, DOM rendering, or screenshot capture is utilized.

6. **Non-Operational Scope Preservation**:
   - All generated CSV files and PDF screening reports explicitly reiterate D-DATO's non-operational status.
   - Terminology strictly adheres to early-stage screening boundaries: *"ranked candidate"*, *"close-approach event"*, and *"early-stage planning aid"*.

---

## Final Backend Architecture & System Boundaries (Phase P18 Freeze)

### 1. End-to-End System Flow Map

```text
       Data Sources (CelesTrak / Space-Track / Offline Fixtures)
                                  │
                                  ▼
                         Ingestion + Cache
                     (Filesystem SHA-256 Cache)
                                  │
                                  ▼
                                  DB
                    (SQLAlchemy 2.x System of Record)
                                  │
                                  ▼
                           Scientific Core
              (SGP4, J2 Secular, Conjunction, Risk, Ranking)
                                  │
                                  ▼
                          Pipeline + Worker
                    (Async Background Execution)
                                  │
                                  ▼
                          Persisted Results
            (Plans, Runs, Candidates, Events, Validations)
                                  │
    ┌────────────────┬────────────┼────────────┬──────────────┬─────────────┐
    ▼                ▼            ▼            ▼              ▼             ▼
Planning/Run   Candidate/Event Heatmap       Globe        Validation     Export
    API              API          API          API           API           API
    └────────────────┴────────────┼────────────┴──────────────┴─────────────┘
                                  │
                                  ▼
                        Future React Frontend
                 (Consumes Frozen REST JSON / Blobs)
```

### 2. Core Architectural Guarantees & Boundaries

1. **FastAPI is the Backend Boundary**:
   - All external client and frontend interactions pass strictly through the versioned HTTP REST interface (`/api/v1/*`).
   - No direct database connections, worker threads, or internal astrodynamics modules are exposed across the boundary.

2. **SQLAlchemy Persistence is the System of Record**:
   - Persisted relational tables (`plans`, `runs`, `candidates`, `conjunction_events`, `debris_objects`, `validation_records`) constitute the authoritative single source of truth.
   - In-memory state is transient; all completed calculations are queryable and reproducible from the database.

3. **Frontend Consumes Persisted API Results**:
   - The frontend is strictly a consumer of finalized JSON representations and binary exports.
   - The frontend never performs orbital mechanics calculations, coordinate transformations, risk calculations, ranking formulas, or fuel budgets.

4. **Scientific Logic Belongs Exclusively to the Backend**:
   - Keplerian-Cartesian conversions, SGP4 orbital propagation, J2 perturbation drift, conjunction screening passes, Golden-section TCA refinement, fuel delta-v budgets, and multi-objective composite risk scoring remain strictly in `app/core` and `app/services`.

5. **Exports are Serialization Only**:
   - Export endpoints (`/runs/{run_id}/exports/csv` and `/runs/{run_id}/exports/pdf`) perform read-only streaming serialization over already-persisted database rows.
   - Exports never trigger worker execution, pipeline runs, SGP4 propagation, or risk recalculation.

6. **Validation is Reference Comparison Only**:
   - The validation service compares already-persisted D-DATO conjunction events against external reference datasets (specifically SOCRATES).
   - Validation does not alter, replace, or rerun D-DATO conjunction screening. It provides comparative audit evidence only.







