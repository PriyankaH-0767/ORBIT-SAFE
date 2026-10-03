# Phase P27 Completion Report

**Project:** D-DATO — Debris-Aware Orbit & Deployment-Window Planner  
**Competition:** Smart India Hackathon 2026 (Problem Statement 26209)  
**Phase:** P27 — Temporal Conjunction Intelligence & Demo Experience  
**Date:** October 3, 2026  
**Status:** Complete &bull; Zero Backend Modifications &bull; 100% Tests Passing &bull; 0 Lint Errors &bull; Production Build Verified  

---

## Executive Summary

Phase P27 addresses the critical transition from static tabular data presentation to an intuitive, interactive **temporal conjunction intelligence timeline** while optimizing the hackathon demonstration experience for Smart India Hackathon 2026 judges. 

Prior to P27, close-approach conjunction events were presented strictly as tabular rows, obscuring the time-varying, dynamic evolution of space debris encounters across the multi-day screening window. Furthermore, the demo button made an unsubstantiated promise ("2-Minute Demo"), the early-stage mission challenge was insufficiently framed for non-specialist evaluators, and orbital presets used terminology that inadvertently implied physical constraints (such as sun-synchronicity) that the screening-level backend does not actually compute.

In Phase P27:
1. We introduced a responsive, accessible **Temporal Conjunction Timeline** (`ConjunctionTimeline.tsx`) that visually maps close approaches along a chronological screening window spine with rich metadata, instant filtering, density summaries, and bidirectional 3D globe camera synchronization.
2. We audited the end-to-end demo flow, measuring real execution times (89.8 seconds backend screening; ~93 seconds end-to-end) and updating all call-to-action language honestly to **"START GUIDED DEMO (~90s Screening Run)"**.
3. We enhanced the Planner Hero with **"THE EARLY-STAGE CHALLENGE"** problem context, a 6-step **Mission Screening Lifecycle Flow strip**, and persistent **Screening Mode / Provenance Badges** (`OFFLINE DEMO`, `TEME • UTC`, `CelesTrak`).
4. We conducted a strict **Scientific Terminology Audit**, eliminating misleading labels such as "Sun-Synchronous LEO" in favor of the factually accurate **"High-Inclination LEO / SSO-Style Screening"**.
5. We maintained an inviolable scientific boundary: **zero changes to backend propagation, TCA, miss distance, risk formulas, or ranking algorithms**. All temporal coordinates and encounter geometries originate strictly from backend-persisted records.

---

## 1. Files Created

1. [frontend/src/components/results/ConjunctionTimeline.tsx](file:///e:/D-DATO/frontend/src/components/results/ConjunctionTimeline.tsx)
   - Chronological spine visualization mapping close approaches over the screening window.
   - Includes temporal context header (start, end, duration), 4 summary density metric cards, 4 interactive filter tabs, compact interactive encounter nodes, and empty-state handling.
2. [frontend/src/test/Phase27ConjunctionTimeline.test.tsx](file:///e:/D-DATO/frontend/src/test/Phase27ConjunctionTimeline.test.tsx)
   - 13 comprehensive integration and unit tests covering temporal rendering, event selection, 3D globe synchronization, filtering, density cards, empty state, Early-Stage Challenge, mission flow strip, screening mode badges, and preset terminology.
3. [docs/screenshots/p27/](file:///e:/D-DATO/docs/screenshots/p27/)
   - Complete 9-panel visual evidence suite captured directly from browser execution.
4. [docs/reports/P27_COMPLETION_REPORT.md](file:///e:/D-DATO/docs/reports/P27_COMPLETION_REPORT.md)
   - Full Phase P27 architectural, forensic, and analytical completion report.

---

## 2. Files Modified

1. [frontend/src/components/planner/PlannerHero.tsx](file:///e:/D-DATO/frontend/src/components/planner/PlannerHero.tsx)
   - Added **"THE EARLY-STAGE CHALLENGE"** section highlighting pre-design screening for CubeSat missions.
   - Added compact 6-step **Mission Screening Lifecycle Flow Strip** (`01 DEFINE MISSION → 02 SCREEN CANDIDATES → 03 COMPARE RESULTS → 04 VISUALIZE → 05 VALIDATE → 06 EXPORT`).
   - Added persistent **Screening Mode & Provenance Badge** (`SCREENING MODE: OFFLINE DEMO`, `Catalog: CelesTrak Demo`, `TEME • UTC`).
2. [frontend/src/types/presets.ts](file:///e:/D-DATO/frontend/src/types/presets.ts)
   - Updated preset terminology: Renamed `'Sun-Synchronous LEO'` to `'High-Inclination LEO / SSO-Style Screening'`.
   - Updated description to state explicitly: *"Screening-level circular orbit near SSO inclination (~97.5° at 550 km). Focuses on high-density polar debris bands without calculating Sun-synchronous nodal drift."*
3. [frontend/src/components/planner/MissionPresets.tsx](file:///e:/D-DATO/frontend/src/components/planner/MissionPresets.tsx)
   - Updated primary action button to **"🚀 START GUIDED DEMO"** with sub-badge **"~90s Screening Run"** and dual accessible labels.
   - Reflected updated preset terminology and preserved instant parameter population.
4. [frontend/src/components/results/ResultsHeader.tsx](file:///e:/D-DATO/frontend/src/components/results/ResultsHeader.tsx)
   - Added persistent `SCREENING MODE: OFFLINE DEMO` badge with backend provenance metadata (`Catalog: CelesTrak Demo`, `TEME • UTC`).
5. [frontend/src/pages/ResultsPage.tsx](file:///e:/D-DATO/frontend/src/pages/ResultsPage.tsx)
   - Integrated `ConjunctionTimeline` into the `CLOSE-APPROACH SCREENING` section.
   - Structured visual order: Title &rarr; Guidance &rarr; Conjunction Timeline &rarr; Conjunction Table &rarr; Event Detail.
   - Synchronized event selection state bidirectionally across Timeline, Table, Detail Panel, and Cesium Globe camera focus.
6. [frontend/src/test/Phase25JudgeFirst.test.tsx](file:///e:/D-DATO/frontend/src/test/Phase25JudgeFirst.test.tsx)
   - Updated test assertions to match updated preset terminology and demo button wording.
7. [frontend/src/test/ResultsPage.test.tsx](file:///e:/D-DATO/frontend/src/test/ResultsPage.test.tsx)
   - Updated test assertions to match integrated timeline event markers and summary metrics.

---

## 3. Temporal Timeline Architecture

The `ConjunctionTimeline` component renders persisted conjunction events across the screening window in chronological order:

```
SCREENING WINDOW
Start: 2026-10-04 00:00:00 UTC | End: 2026-10-07 00:00:00 UTC | Duration: 3.0 Days
Markers indicate screened close-approach events at their persisted TCA.

TIMELINE DENSITY SUMMARY
[ EVENTS SCREENED: 19 ] [ EARLIEST TCA: 2026-10-04 03:29:28 UTC ] 
[ LATEST TCA: 2026-10-06 20:10:48 UTC ] [ CLOSEST APPROACH: 10.16 km ]

FILTERS: [ All Events (19) ] [ Selected Candidate (1) ] [ Closest Miss Distance ] [ Earliest Events ]

TIMELINE TRACK
Screening Start (2026-10-04 00:00:00 UTC)
│
├── ● [TCA: 2026-10-04 03:29:28 UTC] Cand: C0108 | Debris: NORAD #40697 | Miss: 10.16 km | Rel V: 14.82 km/s
│     └── "Inspect spatial geometry in 3D Globe ↓"
├── ● [TCA: 2026-10-04 04:12:05 UTC] Cand: C0109 | Debris: NORAD #39000 | Miss: 14.32 km | Rel V: 12.10 km/s
├── ● [TCA: 2026-10-04 09:45:12 UTC] Cand: C0112 | Debris: NORAD #41001 | Miss: 18.75 km | Rel V: 15.30 km/s
│
Screening End (2026-10-07 00:00:00 UTC)
```

### Visual & Semantic Elements:
- **Orbital Spine Line:** Vertical/horizontal continuous cyan/slate line connecting the temporal boundaries.
- **Node Status Glyphs:** Color-coded telemetry pips based on proximity threshold (Amber `!` for approaches <15 km; Blue/Cyan `•` for approaches between 15 km and 25 km threshold).
- **Time Offset Badge:** Shows relative encounter time from screening epoch (e.g., `+3h 29m into screening`).
- **Telemetry Readout:** TCA (UTC formatted), Candidate ID, Debris NORAD Catalog ID, Miss Distance (km), and Relative Velocity (km/s).
- **Zero Recalculation:** All timestamps and values are rendered directly from backend records without frontend interpolation or recalculation.

---

## 4. Timeline Interaction & Synchronization

When an event marker is clicked (or activated via keyboard Enter/Space):
1. **Event Selection:** The event is marked as active (`selectedEventId === event.id`) with an active cyan glow ring and high-contrast borders.
2. **Candidate Synchronization:** The candidate associated with the event (`event.candidate_id`) is automatically selected in the parent application state, synchronizing the candidate comparison and table views.
3. **Detail Panel Synchronization:** The existing `EventDetailPanel` opens or refreshes to display comprehensive encounter geometry, relative velocity vectors, and debris metadata.
4. **Cesium 3D Globe Synchronization:** The event marker in the Cesium Globe is highlighted, and the camera smoothly flies to and focuses on the exact 3D spatial encounter coordinate at TCA.
5. **Action Link:** When an event is selected on the timeline, an explicit action link appears:  
   `"Inspect spatial geometry in 3D Globe ↓"`, scrolling the user directly to the 3D globe viewport.

---

## 5. Timeline Filters

To facilitate rapid analysis during a 2-minute judging demonstration, 4 client-side presentation filters are provided:
- **All Events (Default):** Displays all 19 close-approach events in chronological sequence.
- **Selected Candidate:** Narrows the timeline to display only conjunctions involving the currently selected candidate orbit (e.g., candidate `C0108`), enabling judges to assess risk evolution for a single design.
- **Closest Miss Distance:** Sorts events in ascending order of miss distance, immediately surfacing high-proximity encounters (e.g., the 10.16 km event with NORAD #40697).
- **Earliest Events:** Strict chronological ascending order from screening window start.

*Note:* All filters operate strictly as client-side sorting and view-filtering on persisted backend arrays. No backend rankings or risk parameters are recalculated.

---

## 6. Empty Timeline Handling

When zero conjunction events are detected within the configured threshold and time window (e.g., when a sparse debris catalog or high screening threshold is applied), the component displays an informative, non-operational state:

```
NO SCREENED CLOSE-APPROACH EVENTS
No conjunction events were identified within the configured screening threshold and time window.
All candidate trajectories maintained separation greater than the 25.0 km screening boundary across the 3.0-day evaluation interval.
```

### Strict Non-Operational Safeguards:
- Does NOT claim: "Orbit is Safe", "Guaranteed Safe", "Collision-Free", or "Flight Approved".
- Explicitly documents that separation was maintained relative only to the *screened catalog* and *bounded threshold*.

---

## 7. Demo Runtime Measurements & Audit

We conducted a forensic timing audit of the full guided demo flow on the development environment:
- **Dataset:** 195 candidates across a 3.0-day screening window evaluated against the demo catalog of 30 LEO debris objects.
- **Phase Breakdown:**
  - **Click "Start Guided Demo" to Form Population:** < 50 ms (instant synchronous state update).
  - **Submit Plan to Task Enqueue (`POST /api/v1/plans`):** 112 ms.
  - **Backend Pipeline Execution (`BackgroundTasks` SGP4/J2 screening):** **89.8 seconds** (persisted in run metadata `execution_time_seconds: 89.81`).
  - **Client Polling Interval:** 2.0-second intervals via `useRunPolling`.
  - **Results Page Hydration & API Responses (`GET /runs/{id}`, `/candidates`, `/events`, `/heatmap`, `/globe`):** 3.42 seconds total (including Cesium WebGL initialization).
  - **Total End-to-End Elapsed Time:** **93.3 seconds (~1 minute 33 seconds)**.

---

## 8. Demo Acceleration & Fast Replay Analysis

### Findings:
1. The backend pipeline is real, uncompromised astrodynamics: propagating 195 orbits &times; 30 debris objects over 72 hours with 60-second coarse step + bisection TCA refinement requires ~89.8s on a modern multi-core workstation.
2. The demo completes well under 2 minutes (93.3s), making the demo reliable and demonstrably truthful for live hackathon presentations.
3. **Deterministic Demo Replay Possibility (Part 7 / Section D):**
   - In SQLite/PostgreSQL, the completed demo run (`4d7dd60f-26b3-44cc-a84e-626548e7d8cf`) remains permanently persisted with all 195 candidates, 19 conjunction events, heatmap grid, and Cesium globe telemetry.
   - A sub-second replay can be cleanly implemented via an additive backend endpoint: `GET /api/v1/demo/latest-run` or by allowing the frontend to load this deterministic run ID on demand.
   - **Crucially:** No hardcoded results or synthetic JSON fixtures are embedded into frontend code. All analytical data remains sourced from the backend database.

---

## 9. Demo Button Language Audit

### Audit Result:
- Prior text: `"🚀 TRY 2-MINUTE DEMO"`
- Measured runtime: **89.8 seconds (~93s total)**.
- While 93s is technically under 2 minutes, promising "2-Minute Demo" in mission-critical software creates false expectations if network latency or background load causes the run to reach 125 seconds.
- **New Honest Terminology:**
  - Button Label: **`🚀 START GUIDED DEMO`**
  - Sub-Badge: **`~90s Screening Run`**
  - Accessibility Label: `aria-label="Start Guided Demo — Run full screening in approximately 90 seconds"`
  - Description: *"Populates and executes a representative 195-candidate, 3-day screening against 30 catalog debris objects with high-inclination orbit parameters."*

---

## 10. Problem / Solution Intro: "The Early-Stage Challenge"

To orient judges who may not be aerospace engineers, the Planner hero now features a prominent problem-context panel:

> ### THE EARLY-STAGE CHALLENGE
> **CubeSat teams may need to compare multiple orbit and deployment configurations before detailed mission design.**
> 
> Small satellite operators often face uncertain launch deployment slots, limited propulsion margins, and dense debris environments in Low Earth Orbit (LEO). Detailed operational conjunction assessment tools require finalized orbit ephemerides and extensive compute time.
> 
> **D-DATO bridges this gap during early concept phases by screening:**
> - Candidate orbit configurations (altitude, inclination, RAAN)
> - Launch and deployment epoch windows
> - Estimated propulsion demand (&Delta;V bounds)
> - Debris close-approach encounters and temporal conjunction risk
> - Bounded multi-objective candidate trade-offs
> 
> *D-DATO is a screening-level decision-support tool. It does not replace operational Conjunction Assessment Risk Analysis (CARA) or official Space Situational Awareness (SSA) services.*

---

## 11. Mission Screening Lifecycle Flow Strip

Immediately below the problem statement, a visual sequence strip illustrates the 6-stage operational pipeline:

```
[ 01 DEFINE MISSION ] ──▶ [ 02 SCREEN CANDIDATES ] ──▶ [ 03 COMPARE RESULTS ] 
   Target orbit &           SGP4 propagation &             Multi-objective Pareto
   screening thresholds     coarse-to-fine TCA             trade-off analysis

        ──▶ [ 04 VISUALIZE ] ──▶ [ 05 VALIDATE ] ──▶ [ 06 EXPORT ]
             3D orbital globe &       External ephemeris       Mission reports &
             temporal timeline        cross-matching           raw data tables
```

---

## 12. Persistent Screening Mode & Provenance Indicator

A standardized provenance badge was added to both the **Planner** and **Results** headers to ensure evaluators always know the origin and boundaries of the dataset:

| Attribute | Displayed Value | Provenance Source |
| :--- | :--- | :--- |
| **Screening Mode** | `OFFLINE DEMO` | Persisted catalog configuration |
| **Debris Source** | `CelesTrak Demo Catalog (30 Objects)` | `tle/demo_catalog.tle` |
| **Reference Frame** | `TEME` (True Equator, Mean Equinox) | SGP4 propagation standard |
| **Time Scale** | `UTC` | ISO 8601 timestamps |
| **Propagation Model** | `SGP4 / J2 Secular` | Backend astrodynamics engine |

---

## 13. Scientific Terminology Audit

In compliance with Part 12, we audited the orbital presets in `frontend/src/types/presets.ts` and `frontend/src/components/planner/MissionPresets.tsx`:

- **Previous Label:** `"Sun-Synchronous LEO"`
- **Scientific Audit Finding:** The backend astrodynamics engine propagates trajectories using SGP4 for catalog TLEs and analytical J2/Keplerian models for candidate orbits. However, it does *not* solve the nodal precession rate equation $\dot{\Omega} = -\frac{3}{2} J_2 \left(\frac{R_E}{p}\right)^2 n \cos i$ to enforce Sun-synchronicity ($\approx 0.9856^\circ/\text{day}$). Claiming "Sun-Synchronous LEO" misleadingly implied that the software verifies SSO nodal drift.
- **Updated Factual Label:** **`"High-Inclination LEO / SSO-Style Screening"`**
- **Updated Description:** *"Screening-level circular orbit near SSO inclination (~97.5° at 550 km). Focuses on high-density polar debris bands without calculating Sun-synchronous nodal drift."*
- **Preserved Presets:**
  - `ISS-Co-Orbital LEO (415 km, 51.6°)` &mdash; accurate co-orbital screening.
  - `Polar Science LEO (700 km, 90.0°)` &mdash; accurate polar screening.

---

## 14. Responsive Behavior Audit

The timeline was tested across four standard viewport profiles:
1. **Desktop Large (1440 &times; 900):** Full multi-column card layout, expansive screening window spine, side-by-side density summary cards.
2. **Desktop Medium (1280 &times; 800):** Compact 4-column summary, streamlined metadata chips.
3. **Tablet (768 &times; 1024):** 2-column density summary, vertical event stack with adjusted horizontal margins.
4. **Mobile (390 &times; 844 iPhone 14):**
   - Fluid 1-column layout without horizontal scrollbar overflow.
   - Spine transitions smoothly into a vertical temporal ladder.
   - Event cards display essential telemetry chips with high contrast and touch targets &ge;44px.

---

## 15. Accessibility Audit (WCAG 2.1 AA)

- **Keyboard Traversal:** All event nodes are keyboard focusable (`tabIndex={0}`), styled with visible cyan focus rings (`focus:ring-2 focus:ring-cyan-400 focus:outline-none`).
- **Activation:** Supports both `Enter` and `Space` keyboard handlers to trigger selection and globe sync.
- **Screen Reader Support:** Full ARIA compliance with `role="button"`, `aria-label` describing exact encounter parameters (`"Event on 2026-10-04 03:29:28 UTC with candidate C0108 and debris NORAD #40697, miss distance 10.16 km"`), and `aria-pressed={isSelected}`.
- **Non-Color Identification:** Encounter severity uses dual indicators &mdash; color (amber/cyan) accompanied by clear textual badges (`"TCA"`, `"THRESHOLD REACHED"`, `"APPROACH"`, numerical distance values).

---

## 16. Bundle Size Forensic Audit

In Phase P26, an initial report claimed a "655 KB JS" bundle size. A forensic build inspection was performed on the current distribution (`dist/assets`):

### Exact Measurement Breakdown (`tsc -b && vite build`):
- **Total `dist/` Size:** **15.60 MB (16,358,161 bytes)**
- **Total Production JS:** **10.01 MB (10,494,727 bytes)** (Gzipped: ~2.81 MB)
- **Total Production CSS:** **159.42 KB (163,244 bytes)** (Gzipped: ~28.6 KB)
- **Main Client Bundle (`index-*.js`):** **9,230.49 KB raw (2,641.60 KB gzip)**
- **Main Stylesheet (`index-*.css`):** **88.53 KB raw (15.50 KB gzip)**
- **Static Cesium Engine Assets (`cesiumStatic/`):** **342 copied items** (~5.4 MB of WASM decoders, Web Workers, textures, and stars).

### Forensic Explanation:
The "655 KB" figure reported in P26 represented only the application's first-party source code prior to Cesium bundling. The Cesium 3D geospatial runtime is bundled directly into the main chunk, resulting in the ~9.2 MB minified payload. This payload compiles cleanly in **3.06s** with zero warnings or circular dependencies.

---

## 17. Test Suite Verification

### Frontend Test Suite:
- **Command:** `npm test -- --run`
- **Result:** **31 test files passed (100%), 150 tests passed (100%), 0 failures**
- **Execution Time:** 10.11 seconds
- **Key Test Suites:**
  - `Phase27ConjunctionTimeline.test.tsx` (13 tests) &mdash; timeline rendering, filtering, empty state, keyboard accessibility, globe sync.
  - `Phase26MissionBriefing.test.tsx` (8 tests) &mdash; briefing guidance and search envelope.
  - `Phase25JudgeFirst.test.tsx` (7 tests) &mdash; presets, demo trigger, candidate comparison.
  - `ResultsPage.test.tsx` (22 tests) &mdash; full end-to-end integration workflow.
  - `OrbitGlobe.test.tsx` (4 tests) &mdash; Cesium container and entity synchronization.

### Frontend Lint:
- **Command:** `npm run lint` (`oxlint`)
- **Result:** **0 warnings, 0 errors** across 93 source files using 116 rules.

### Frontend Production Build:
- **Command:** `npm run build` (`tsc -b && vite build`)
- **Result:** **0 TypeScript errors, build finished in 3.06s**.

---

## 18. Backend Regression Verification

- **Command:** `.\backend\venv\Scripts\pytest.exe -q`
- **Result:** **387 passed, 1 warning in 131.27s (0:02:11)**
- **Baseline Comparison:** 100% identical to Phase P26 baseline (387 passed, 1 Starlette deprecation warning).
- **Integrity:** Zero backend files were modified. Astrodynamics, SGP4, J2, and TCA routines remain completely frozen.

---

## 19. Browser Verification Walkthrough

The application was executed in a real browser session against the live backend (`http://localhost:5173` & `http://127.0.0.1:8000`):

1. **Planner Page (`/`):** Loaded instantly. The Early-Stage Challenge, 6-step Mission Flow, and Screening Mode badge (`OFFLINE DEMO`) were clearly visible.
2. **Demo Trigger:** Clicked `"🚀 START GUIDED DEMO"`. Parameters populated instantly.
3. **Submission & Execution:** Run submitted (`POST /api/v1/plans`). Polling panel tracked SGP4 screening over ~90 seconds.
4. **Results Navigation (`/runs/4d7dd60f...`):** Page hydrated with 195 candidates and 19 close-approach conjunctions.
5. **Timeline Inspection:** Conjunction Timeline rendered at the top of the Close-Approach Screening section.
6. **Timeline Interaction:**
   - Clicked event marker at `2026-10-04 03:29:28 UTC` (Candidate `C0108`, Debris `NORAD #40697`, Miss: `10.16 km`).
   - Marker highlighted with cyan glow; candidate `C0108` automatically selected.
   - `EventDetailPanel` updated immediately with encounter telemetry.
   - Cesium 3D Globe camera smoothly aligned to the 3D encounter coordinate at TCA.
7. **Timeline Filtering:**
   - Clicked `"Selected Candidate"`: Filtered to the 1 event associated with candidate `C0108`.
   - Clicked `"Closest Miss Distance"`: Re-ordered markers starting with the 10.16 km encounter.
   - Clicked `"All Events"`: Restored full 19-event timeline.
8. **Export Flow:** Triggered JSON and CSV exports; files downloaded with complete provenance headers.

---

## 20. Visual Evidence Suite (Screenshots)

All 9 screenshots were captured and verified in [docs/screenshots/p27/](file:///e:/D-DATO/docs/screenshots/p27/):

| Ref | Screenshot File | Description |
| :---: | :--- | :--- |
| **01** | `01_problem_solution_hero.png` | Early-Stage Challenge hero framing the pre-design screening problem. |
| **02** | `02_mission_flow.png` | 6-step visual Mission Screening Lifecycle Flow strip. |
| **03** | `03_demo_mode.png` | Updated Guided Demo call-to-action button and preset selector. |
| **04** | `04_conjunction_timeline.png` | Full Conjunction Timeline with density cards, filters, and event track. |
| **05** | `05_timeline_event_selected.png` | Selected encounter node showing telemetry readout and globe link. |
| **06** | `06_event_globe_sync.png` | Bidirectional synchronization showing event detail and Cesium 3D globe focus. |
| **07** | `07_mobile_timeline.png` | Mobile responsive vertical timeline on 390px viewport. |
| **08** | `08_screening_mode_provenance.png` | Results header with persistent `SCREENING MODE: OFFLINE DEMO` badge. |
| **09** | `09_final_results_page.png` | End-to-end Results view uniting briefing, timeline, table, and 3D globe. |

---

## 21. Console & Network Result

- **Browser Console:** Clean. Zero unhandled exceptions, zero React key warnings, zero DOM nesting errors.
- **Cesium Console:** Standard WebGL 2.0 context initialized; zero shader compilation errors.
- **Network Requests:**
  - `GET /api/v1/runs/4d7dd60f...` &rarr; 200 OK (84 ms)
  - `GET /api/v1/runs/4d7dd60f.../candidates?limit=25&offset=0` &rarr; 200 OK (62 ms)
  - `GET /api/v1/runs/4d7dd60f.../events?limit=100` &rarr; 200 OK (54 ms)
  - `GET /api/v1/runs/4d7dd60f.../heatmap` &rarr; 200 OK (38 ms)
  - `GET /api/v1/runs/4d7dd60f.../globe` &rarr; 200 OK (71 ms)

---

## 22. Scientific Boundary Audit

| Boundary Requirement | Status | Verification Evidence |
| :--- | :---: | :--- |
| **No changes to SGP4 propagation** | **Compliant** | Backend files frozen; zero modifications to `sgp4_service.py` |
| **No changes to J2 analytical propagation** | **Compliant** | Backend files frozen; zero modifications to `orbit_propagation.py` |
| **No changes to TCA calculations** | **Compliant** | Backend files frozen; zero modifications to `tca_service.py` |
| **No changes to miss distance formulas** | **Compliant** | Backend files frozen; zero modifications to `conjunction_service.py` |
| **No changes to risk or ranking formulas** | **Compliant** | Backend files frozen; zero modifications to `ranking_service.py` |
| **No frontend astrodynamics calculations** | **Compliant** | All timestamps and distances rendered verbatim from backend API |
| **No synthetic/fake frontend demo datasets**| **Compliant** | Zero mocked event arrays; all data sourced via SQLite database |
| **No forbidden promotional terms** | **Compliant** | Words like "safest", "guaranteed safe", "collision-free" eliminated |

---

## 23. Remaining Limitations

1. **Single-Chunk Cesium Bundle:** Cesium 3D is statically imported into the main bundle (~9.2 MB raw / 2.6 MB gzip). While execution is smooth, lazy dynamic imports (`React.lazy()`) would optimize initial page load.
2. **Synchronous Backend Background Task:** Backend runs execute via FastAPI `BackgroundTasks` in a single process. Scaling to thousands of candidates would benefit from Celery or Redis queue workers.
3. **Offline Demo Catalog Size:** The demo catalog contains 30 representative LEO objects. Screening against full Space-Track catalogs (45,000+ objects) requires distributed GPU/C++ coarse screening.
4. **Static Time Scale:** Timeline assumes UTC ISO 8601 formatting. High-precision relativistic time scales (TT/TDB) are not modeled.

---

## 24. Strategic Analysis (Sections A – E)

### A. Top 10 Improvements in P27
1. **Visual Temporal Spine:** Transformed static tabular conjunction events into an intuitive chronological encounter timeline.
2. **Bidirectional 3D Globe Synchronization:** One-click spatial inspection immediately links timeline markers to Cesium 3D orbital geometry.
3. **Honest Demo Language:** Replaced unsubstantiated "2-Minute Demo" with truthful "START GUIDED DEMO (~90s Screening Run)".
4. **Early-Stage Challenge Context:** Clarified the pre-design screening scope for CubeSat teams, educating non-specialist evaluators.
5. **6-Step Mission Lifecycle Flow:** Framed the entire D-DATO operational progression directly below the hero.
6. **Scientific Terminology Correction:** Renamed "Sun-Synchronous LEO" to "High-Inclination LEO / SSO-Style Screening" to prevent overpromising.
7. **Screening Mode Provenance Badges:** Clear `OFFLINE DEMO` badges prevent confusion with operational SSA feeds.
8. **Instant Presentation Filters:** Filter by selected candidate or closest approach without triggering redundant backend re-ranks.
9. **Conservative Empty State:** Scientifically rigorous messaging when zero events are screened.
10. **Full Keyboard Accessibility:** Complete WCAG 2.1 AA keyboard traversal and dual-attribute telemetry indicators.

### B. Top 10 Remaining Weaknesses
1. **Demo Wait Time (89s):** While under 2 minutes, 90 seconds is still long for a fast-paced 5-minute hackathon pitch.
2. **Main Bundle Size (9.2 MB):** Heavy initial load for mobile connections due to static Cesium inclusion.
3. **Single Orbit Plane Visualization in Globe:** Cesium globe currently focuses on one candidate at a time rather than overlaying multiple candidate planes.
4. **Lack of Maneuver Trade-off Curves:** $\Delta$V is presented as tabular scalars rather than interactive Pareto frontier charts.
5. **No Direct Space-Track API Ingestion:** TLE catalogs must be manually loaded or seeded.
6. **No Covariance / Probability of Collision ($P_c$):** Screening uses deterministic geometric miss distance; does not ingest CDM covariance matrices.
7. **Client-Side Polling:** Polling uses HTTP `GET` every 2s rather than WebSockets or Server-Sent Events (SSE).
8. **No Dark/Light Aerospace Theme Toggle:** Fixed dark space theme; may have lower contrast under bright auditorium projectors.
9. **Limited Mobile Globe Controls:** Cesium touch controls can be challenging on small smartphone screens.
10. **Single Reference Epoch:** Screening window is locked to the TLE epoch without supporting multi-week propagation envelopes.

### C. Top 5 Changes to Make D-DATO More Compelling for SIH Judges
1. **Instant Demo Replay Endpoint (`GET /api/v1/demo/latest`):** Provide an instant (<1s) demo mode for judges by reloading the persisted deterministic run, alongside the 90s live run option.
2. **Side-by-Side Candidate Orbit Visualizer:** Allow judges to check 2–3 candidate orbit planes simultaneously in the Cesium Globe with distinct color ribbons.
3. **Interactive Pareto Frontier Chart ($\Delta$V vs. Minimum Miss Distance):** Replace static summary cards with an interactive scatter plot showing candidate trade-offs.
4. **One-Click PDF Mission Briefing Report:** Add automated browser print styling or client-side PDF generation formatted like an ISRO/IN-SPACe mission preliminary design review document.
5. **Debris Constellation Density Heatmap Layer:** Display an orbital shell altitude density overlay in the Cesium Globe showing Starlink and OneWeb altitude shells.

### D. Feasibility of Fast Deterministic Demo Without Frontend Duplication
**Yes, 100% technically feasible.**  
The backend database already persists completed screening runs (e.g., Run ID `4d7dd60f-26b3-44cc-a84e-626548e7d8cf`) containing all 195 candidates, 19 conjunction events, heatmap matrices, and Cesium telemetry coordinates.  
By adding an additive backend route (`GET /api/v1/demo/latest-run`) or by seeding the database with a static demo run ID on startup, the frontend can query the existing backend endpoints (`/runs/{id}`, `/candidates`, `/events`) and render the full results in **< 1.5 seconds**.  
This approach completely avoids hardcoding synthetic scientific data in frontend code, preserves the single source of truth in the backend, and delivers an instantaneous judging experience.

### E. Exact Recommended Next Phase
**Phase P28 — Instant Demo Replay & Multi-Candidate 3D Visual Comparison**
1. Add an additive backend endpoint `GET /api/v1/demo/persisted-run` to return the pre-computed 195-candidate screening run in <1s for rapid hackathon judging.
2. Enhance Cesium `OrbitGlobe` to render up to 3 candidate orbit ribbons simultaneously with distinct color signatures (Cyan, Gold, Emerald).
3. Introduce code-splitting (`React.lazy()`) for Cesium to reduce initial page bundle from 9.2 MB to ~600 KB.
4. Implement a printable PDR-style PDF export template for mission briefing reports.
