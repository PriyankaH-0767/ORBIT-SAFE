"""Candidate ranking service for D-DATO.

Phase P10: Coordinates multi-objective ranking of candidate deployment options
using normalized fuel cost and risk score.
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union
from sqlalchemy.orm import Session

from app.core.ranking import RankedCandidate, rank_candidates
from app.db.repositories import CandidateRepository


class RankingService:
    """Service calculating composite multi-objective scores for deployment candidates."""

    def rank_candidates(
        self,
        candidates: Sequence[Any],
        fuel_estimates: Union[Mapping[str, Any], Sequence[Any]],
        risk_assessments: Union[Mapping[str, Any], Sequence[Any]],
        fuel_weight: Optional[float] = None,
        risk_weight: Optional[float] = None,
    ) -> List[RankedCandidate]:
        """Rank candidate deployment options without database persistence."""
        return rank_candidates(
            candidates=candidates,
            fuel_estimates=fuel_estimates,
            risk_assessments=risk_assessments,
            fuel_weight=fuel_weight,
            risk_weight=risk_weight,
        )

    def rank_and_persist(
        self,
        db: Session,
        candidates: Sequence[Any],
        fuel_estimates: Union[Mapping[str, Any], Sequence[Any]],
        risk_assessments: Union[Mapping[str, Any], Sequence[Any]],
        fuel_weight: Optional[float] = None,
        risk_weight: Optional[float] = None,
    ) -> List[RankedCandidate]:
        """Rank candidate deployment options and persist ranks atomically in database."""
        ranked = self.rank_candidates(
            candidates=candidates,
            fuel_estimates=fuel_estimates,
            risk_assessments=risk_assessments,
            fuel_weight=fuel_weight,
            risk_weight=risk_weight,
        )
        if ranked:
            repo = CandidateRepository(db)
            rank_map = {rc.candidate_id: rc.rank for rc in ranked}
            repo.bulk_update_ranks(rank_map)
        return ranked

    def score_and_rank(
        self,
        candidates: Sequence[Any],
        fuel_estimates: Union[Mapping[str, Any], Sequence[Any]],
        risk_assessments: Union[Mapping[str, Any], Sequence[Any]],
        db: Optional[Session] = None,
        fuel_weight: Optional[float] = None,
        risk_weight: Optional[float] = None,
    ) -> List[RankedCandidate]:
        """High-level scoring and ranking convenience method with optional DB persistence."""
        if db is not None:
            return self.rank_and_persist(
                db=db,
                candidates=candidates,
                fuel_estimates=fuel_estimates,
                risk_assessments=risk_assessments,
                fuel_weight=fuel_weight,
                risk_weight=risk_weight,
            )
        return self.rank_candidates(
            candidates=candidates,
            fuel_estimates=fuel_estimates,
            risk_assessments=risk_assessments,
            fuel_weight=fuel_weight,
            risk_weight=risk_weight,
        )
