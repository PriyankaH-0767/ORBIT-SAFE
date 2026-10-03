"""Portable Deterministic Demo Service for D-DATO (Phase P28).

Architecture: Option C — Deterministic backend fixture.

At application startup (or on first request), the demo service checks whether a canonical
demo run already exists in the current SQLite database. If not found, it executes the
real D-DATO pipeline synchronously using the fixed demo plan parameters from
`demo_data/demo_catalog.json` and the TLEs in `demo_data/tle/demo_catalog.tle`.

The canonical run ID is cached in memory (``_DEMO_RUN_ID``) so subsequent requests to
GET /api/v1/demo/run are sub-millisecond.

Design guarantees:
- Works after fresh clone + backend setup (no developer database required).
- No SQLite file shipped in version control — the demo run is re-generated on first request.
- No scientific values are hardcoded in frontend code.
- Uses the identical pipeline, TCA solver, risk ranker, and heatmap generator as every
  normal run.
- The result is tagged demo=True via the Plan.demo_mode flag.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.demo_loader import load_demo_plan
from app.db.database import SessionLocal
from app.db.models import Plan, Run, RunStatus
from app.services.run_service import RunService

logger = logging.getLogger(__name__)

# ── In-memory cache ────────────────────────────────────────────────────────────
_DEMO_RUN_ID: Optional[str] = None
_DEMO_LOCK = threading.Lock()

# Stable label embedded in the Plan message so we can find it after restart
DEMO_RUN_MARKER = "CANONICAL_DEMO_RUN_P28"


def _find_existing_demo_run(db: Session) -> Optional[str]:
    """Return the run_id of the most recent completed canonical demo run, or None."""
    # 1. Prefer canonical marked demo run
    stmt = (
        select(Run)
        .join(Plan, Run.plan_id == Plan.id)
        .where(
            Plan.demo_mode.is_(True),
            Run.status == RunStatus.completed.value,
            Run.message == DEMO_RUN_MARKER,
        )
        .order_by(Run.created_at.desc())
    )
    run = db.scalars(stmt).first()
    if run:
        return run.id

    # 2. Fall back to any completed demo_mode run
    stmt_any = (
        select(Run)
        .join(Plan, Run.plan_id == Plan.id)
        .where(
            Plan.demo_mode.is_(True),
            Run.status == RunStatus.completed.value,
        )
        .order_by(Run.created_at.desc())
    )
    run_any = db.scalars(stmt_any).first()
    if run_any:
        return run_any.id

    return None


def _create_demo_run(db: Session, run_service: Optional[RunService] = None) -> str:
    """Execute the full D-DATO pipeline for the canonical demo plan and return the run_id."""
    raw_plan_data = load_demo_plan()
    plan_data = dict(raw_plan_data)
    epoch_raw = plan_data.get("epoch_start")
    if isinstance(epoch_raw, str):
        plan_data["epoch_start"] = datetime.fromisoformat(epoch_raw.replace("Z", "+00:00"))
    elif epoch_raw is None:
        plan_data["epoch_start"] = datetime.now(timezone.utc)

    plan_data["demo_mode"] = True
    plan_data["data_source"] = "demo"

    svc = run_service or RunService()

    # Create plan + queued run
    plan = svc.create_plan(plan_data, db=db)
    run = svc.create_run(plan.id, db=db)
    run_id = run.id

    logger.info(
        "Demo service: executing canonical demo run '%s'…", run_id
    )

    # Execute synchronously in the current thread
    svc.execute_run(run_id, db=db)

    # Stamp the canonical marker so we can rediscover this run after a restart
    run_rec = db.get(Run, run_id)
    if run_rec:
        run_rec.message = DEMO_RUN_MARKER
        db.commit()

    logger.info("Demo service: canonical demo run '%s' completed and stamped.", run_id)
    return run_id


def get_or_create_demo_run(
    db: Optional[Session] = None,
    run_service: Optional[RunService] = None,
) -> str:
    """Return the canonical demo run_id, creating it on first call.

    Thread-safe.
    """
    global _DEMO_RUN_ID

    if db is not None:
        existing = _find_existing_demo_run(db)
        if existing:
            _DEMO_RUN_ID = existing
            return existing
        created_id = _create_demo_run(db, run_service=run_service)
        _DEMO_RUN_ID = created_id
        return created_id

    # Fast path — already cached
    if _DEMO_RUN_ID is not None:
        return _DEMO_RUN_ID

    with _DEMO_LOCK:
        # Double-checked locking
        if _DEMO_RUN_ID is not None:
            return _DEMO_RUN_ID

        with SessionLocal() as db_session:
            existing = _find_existing_demo_run(db_session)
            if existing:
                logger.info("Demo service: rediscovered existing demo run '%s'.", existing)
                _DEMO_RUN_ID = existing
                return _DEMO_RUN_ID

            # No existing demo run — create one
            _DEMO_RUN_ID = _create_demo_run(db_session, run_service=run_service)

    return _DEMO_RUN_ID


def warm_demo_cache() -> None:
    """Attempt to warm the demo run cache at application startup.

    Runs in a background thread so startup latency is not affected.
    If it fails (e.g. data files missing) the error is logged but not raised.
    """
    def _warm() -> None:
        try:
            run_id = get_or_create_demo_run()
            logger.info("Demo warm-cache: demo run '%s' ready.", run_id)
        except Exception as exc:
            logger.warning(
                "Demo warm-cache: could not pre-build demo run (%s). "
                "The demo will be built on first request instead.",
                exc,
            )

    t = threading.Thread(target=_warm, daemon=True, name="demo-warm-cache")
    t.start()
