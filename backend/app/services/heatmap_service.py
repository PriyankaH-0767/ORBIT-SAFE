"""Heatmap matrix calculation service (Phase P14).

The original D-DATO specification is authoritative.
Aggregates persisted candidate deployment orbits into 2D risk heatmap slices:
- X axis: delay_minutes
- Y axis: altitude_km
- Slice dimension: inclination_deg
Values represent persisted Candidate.risk_score (0-100 scale).
Missing grid positions are represented as null (None).
"""

from contextlib import contextmanager
import math
from typing import Callable, Dict, Generator, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Candidate, ConjunctionEvent, Run
from app.db.repositories import CandidateRepository, RunRepository
from app.schemas.heatmap import HeatmapCell, HeatmapLayer, HeatmapResponse


def _coord_key(val: float) -> float:
    """Canonical rounding key to avoid floating-point representation precision drift."""
    return round(float(val), 4)


class HeatmapService:
    """Service providing read-only 2D risk heatmap matrices from persisted candidates."""

    def __init__(self, session_factory: Optional[Callable[[], Session]] = None):
        self.session_factory = session_factory or SessionLocal

    @contextmanager
    def _get_session(self, db: Optional[Session] = None) -> Generator[Session, None, None]:
        if db is not None:
            yield db
        else:
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

    def get_run_heatmap(
        self,
        run_id: str,
        inclination_deg: Optional[float] = None,
        db: Optional[Session] = None,
    ) -> HeatmapResponse:
        """Retrieve 2D risk heatmap matrix for a run, optionally sliced by inclination.

        Strictly read-only: does not trigger screening, worker execution, or recomputation.
        """
        with self._get_session(db) as session:
            run_repo = RunRepository(session)
            run = run_repo.get_by_id(run_id)
            if not run:
                raise ValueError(f"Run '{run_id}' not found.")

            cand_repo = CandidateRepository(session)
            all_candidates = cand_repo.list_by_run_for_heatmap(run_id=run_id)

            # If no candidates are yet persisted (queued, running, or empty result):
            if not all_candidates:
                return HeatmapResponse(
                    run_id=run.id,
                    status=run.status,
                    metric="risk_score",
                    x_axis="delay_minutes",
                    y_axis="altitude_km",
                    inclination_values_deg=[],
                    layers=[],
                    total_candidates=0,
                    populated_cells=0,
                    min_risk_score=None,
                    max_risk_score=None,
                )

            # Efficiently read per-candidate conjunction event statistics in a single aggregate query
            event_stats_stmt = (
                select(
                    ConjunctionEvent.candidate_id,
                    func.count(ConjunctionEvent.id),
                    func.min(ConjunctionEvent.miss_distance_km),
                )
                .where(ConjunctionEvent.run_id == run_id)
                .group_by(ConjunctionEvent.candidate_id)
            )
            event_rows = session.execute(event_stats_stmt).all()
            event_stats: Dict[str, Tuple[int, Optional[float]]] = {
                str(row[0]): (int(row[1]), float(row[2]) if row[2] is not None else None)
                for row in event_rows
                if row[0] is not None
            }

            # Derive sorted distinct grid coordinates across the run's candidates
            # (Preserving exact float values as persisted in the DB)
            alt_map: Dict[float, float] = {}
            for c in all_candidates:
                k = _coord_key(c.altitude_km)
                if k not in alt_map:
                    alt_map[k] = c.altitude_km
            sorted_alt_keys = sorted(alt_map.keys())
            run_altitudes: List[float] = [alt_map[k] for k in sorted_alt_keys]

            delay_map: Dict[float, float] = {}
            for c in all_candidates:
                k = _coord_key(c.deployment_delay_minutes)
                if k not in delay_map:
                    delay_map[k] = c.deployment_delay_minutes
            sorted_delay_keys = sorted(delay_map.keys())
            run_delays: List[float] = [delay_map[k] for k in sorted_delay_keys]

            # Group candidates by inclination slice
            inc_to_cands: Dict[float, List[Candidate]] = {}
            inc_exact_val: Dict[float, float] = {}
            for c in all_candidates:
                inc_k = _coord_key(c.inclination_deg)
                if inc_k not in inc_to_cands:
                    inc_to_cands[inc_k] = []
                    inc_exact_val[inc_k] = c.inclination_deg
                inc_to_cands[inc_k].append(c)

            all_sorted_inc_keys = sorted(inc_to_cands.keys())

            # Filter by inclination_deg if provided
            if inclination_deg is not None:
                target_key = _coord_key(inclination_deg)
                selected_inc_keys = [
                    k for k in all_sorted_inc_keys if math.isclose(k, target_key, abs_tol=1e-4)
                ]
            else:
                selected_inc_keys = all_sorted_inc_keys

            layers: List[HeatmapLayer] = []
            returned_candidates_count = 0
            populated_cells_count = 0
            all_populated_scores: List[float] = []

            for inc_k in selected_inc_keys:
                layer_cands = inc_to_cands[inc_k]
                layer_inc = inc_exact_val[inc_k]

                # Map (alt_key, delay_key) -> Candidate
                cand_grid: Dict[Tuple[float, float], Candidate] = {
                    (_coord_key(c.altitude_km), _coord_key(c.deployment_delay_minutes)): c
                    for c in layer_cands
                }

                # Build 2D matrix: shape = [len(run_altitudes)][len(run_delays)]
                # values[r][c] corresponds to run_altitudes[r] and run_delays[c]
                matrix_values: List[List[Optional[float]]] = []
                for alt_k in sorted_alt_keys:
                    row_values: List[Optional[float]] = []
                    for delay_k in sorted_delay_keys:
                        cand = cand_grid.get((alt_k, delay_k))
                        if cand is not None and cand.risk_score is not None:
                            val = float(cand.risk_score)
                            row_values.append(val)
                            populated_cells_count += 1
                            all_populated_scores.append(val)
                        else:
                            row_values.append(None)
                    matrix_values.append(row_values)

                # Build detailed cells list for candidates in this layer,
                # sorted by altitude ASC, delay ASC
                sorted_layer_cands = sorted(
                    layer_cands,
                    key=lambda c: (_coord_key(c.altitude_km), _coord_key(c.deployment_delay_minutes)),
                )
                layer_cells: List[HeatmapCell] = []
                for c in sorted_layer_cands:
                    returned_candidates_count += 1
                    evt_count, min_miss = event_stats.get(c.id, (0, None))
                    layer_cells.append(
                        HeatmapCell(
                            candidate_id=c.id,
                            altitude_km=c.altitude_km,
                            inclination_deg=c.inclination_deg,
                            delay_minutes=c.deployment_delay_minutes,
                            risk_score=float(c.risk_score) if c.risk_score is not None else None,
                            rank=c.rank,
                            delta_v_m_s=c.delta_v_m_s,
                            within_dv_budget=c.within_dv_budget,
                            accepted_event_count=evt_count,
                            minimum_miss_distance_km=min_miss,
                            uncertainty_level="nominal",
                        )
                    )

                layers.append(
                    HeatmapLayer(
                        inclination_deg=layer_inc,
                        altitude_values_km=list(run_altitudes),
                        delay_values_minutes=list(run_delays),
                        values=matrix_values,
                        cells=layer_cells,
                    )
                )

            min_risk = min(all_populated_scores) if all_populated_scores else None
            max_risk = max(all_populated_scores) if all_populated_scores else None

            return HeatmapResponse(
                run_id=run.id,
                status=run.status,
                metric="risk_score",
                x_axis="delay_minutes",
                y_axis="altitude_km",
                inclination_values_deg=[layer.inclination_deg for layer in layers],
                layers=layers,
                total_candidates=returned_candidates_count,
                populated_cells=populated_cells_count,
                min_risk_score=min_risk,
                max_risk_score=max_risk,
            )

    def generate_heatmap(self, run_id: str) -> HeatmapResponse:
        """Deprecated compatibility method delegating to get_run_heatmap."""
        return self.get_run_heatmap(run_id=run_id)


_heatmap_service_instance: Optional[HeatmapService] = None


def get_heatmap_service() -> HeatmapService:
    """Dependency provider returning singleton HeatmapService instance."""
    global _heatmap_service_instance
    if _heatmap_service_instance is None:
        _heatmap_service_instance = HeatmapService()
    return _heatmap_service_instance
