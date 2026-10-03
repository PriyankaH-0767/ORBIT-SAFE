"""Export Service for generating downloadable CSV datasets and PDF screening reports (Phase P17).

NON-OPERATIONAL POSITIONING:
D-DATO is an early-stage screening/planning aid. It is NOT a certified collision-probability
system, operational conjunction assessment tool, maneuver planner, CDM generator, or launch
COLA system. Exports are strictly read-only serialization over persisted database results.
No scientific recomputation, worker submission, or external network access is triggered.
"""

from __future__ import annotations

from contextlib import contextmanager
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
import io
import logging
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple
import zipfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.db.database import SessionLocal
from app.db.models import (
    Candidate,
    ConjunctionEvent,
    DataSnapshot,
    Plan,
    Run,
    ValidationRecord,
)
from app.services.validation_service import ValidationService, get_validation_service
from app.utils.time import format_iso_utc, now_utc

logger = logging.getLogger(__name__)

NON_OPERATIONAL_DISCLAIMER = (
    "NON-OPERATIONAL NOTICE: D-DATO is an early-stage screening/planning aid. "
    "It is not a certified collision-probability system, operational conjunction "
    "assessment tool, maneuver planner, CDM generator, or launch COLA system."
)

PLAN_CSV_HEADERS = [
    "plan_id",
    "run_id",
    "created_at",
    "epoch_start",
    "altitude_min_km",
    "altitude_max_km",
    "altitude_step_km",
    "inclination_min_deg",
    "inclination_max_deg",
    "inclination_step_deg",
    "raan_deg",
    "u0_deg",
    "delay_min_minutes",
    "delay_max_minutes",
    "delay_step_minutes",
    "raan_delay_coupling_deg_per_min",
    "screening_days",
    "reference_altitude_km",
    "reference_inclination_deg",
    "dv_budget_m_s",
    "spacecraft_mass_kg",
    "isp_seconds",
    "fuel_weight",
    "risk_weight",
    "data_source",
    "demo_mode",
    "export_generated_at",
]

CANDIDATES_CSV_HEADERS = [
    "candidate_id",
    "run_id",
    "rank",
    "altitude_km",
    "inclination_deg",
    "raan_deg",
    "u0_deg",
    "deployment_delay_minutes",
    "deployment_epoch",
    "delta_v_m_s",
    "propellant_mass_kg",
    "fuel_fraction",
    "within_dv_budget",
    "risk_score",
    "accepted_event_count",
    "minimum_miss_distance_km",
    "uncertainty_level",
    "composite_score",
]

EVENTS_CSV_HEADERS = [
    "event_id",
    "run_id",
    "candidate_id",
    "debris_object_id",
    "debris_norad_id",
    "tca",
    "miss_distance_km",
    "relative_velocity_km_s",
    "threshold_km",
    "screening_source",
]

VALIDATION_SUMMARY_HEADERS = [
    "validation_id",
    "run_id",
    "status",
    "source",
    "source_fetched_at",
    "validation_created_at",
    "d_dato_event_count",
    "external_event_count",
    "matched_event_count",
    "d_dato_only_count",
    "external_only_count",
    "external_coverage_percent",
    "d_dato_match_rate_percent",
    "mean_abs_tca_error_seconds",
    "max_abs_tca_error_seconds",
    "mean_abs_miss_distance_difference_km",
    "max_abs_miss_distance_difference_km",
]

VALIDATION_MATCHES_HEADERS = [
    "d_dato_event_id",
    "external_event_id",
    "candidate_id",
    "debris_norad_id",
    "tca_d_dato",
    "tca_external",
    "tca_error_seconds",
    "miss_distance_d_dato_km",
    "miss_distance_external_km",
    "miss_distance_difference_km",
    "match_criteria",
]


class RunNotFoundError(ValueError):
    """Raised when the specified run_id is not found in the persistence store."""

    def __init__(self, run_id: str):
        super().__init__(f"Run '{run_id}' not found.")
        self.run_id = run_id


class ExportGenerationError(RuntimeError):
    """Raised when an internal error occurs during export serialization."""
    pass


@dataclass(frozen=True)
class ExportArtifact:
    """Downloadable file payload with appropriate HTTP response metadata."""

    content: bytes
    media_type: str
    filename: str


class NumberedCanvas(canvas.Canvas):
    """Two-pass ReportLab canvas adding accurate total page counts and running header/footers."""

    def __init__(self, *args: Any, **kwargs: Any):
        kwargs["pageCompression"] = 0
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))

        # Running header on pages > 1
        if self._pageNumber > 1:
            self.drawString(
                36,
                755,
                "D-DATO Screening Report — Debris-Aware Orbit & Deployment-Window Planner",
            )
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 750, 576, 750)

        # Running footer
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 42, 576, 42)
        self.drawString(
            36,
            30,
            "NON-OPERATIONAL SCREENING AID — NOT CERTIFIED FOR OPERATIONAL CONJUNCTION ASSESSMENT",
        )
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 30, page_str)
        self.restoreState()


class ExportService:
    """Service generating read-only downloadable CSV archives and PDF reports."""

    def __init__(
        self,
        session_factory: Optional[Callable[[], Session]] = None,
        validation_service: Optional[ValidationService] = None,
    ):
        self.session_factory = session_factory or SessionLocal
        self.validation_service = validation_service or get_validation_service()

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

    def _serialize_csv(self, headers: List[str], rows: List[List[Any]]) -> bytes:
        """Deterministically serialize headers and typed rows to UTF-8 CSV bytes."""
        out = io.StringIO(newline="")
        writer = csv.writer(out, delimiter=",", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        writer.writerow(headers)
        for row in rows:
            formatted_row: List[str] = []
            for val in row:
                if val is None:
                    formatted_row.append("")
                elif isinstance(val, bool):
                    formatted_row.append("true" if val else "false")
                elif isinstance(val, datetime):
                    formatted_row.append(format_iso_utc(val))
                else:
                    formatted_row.append(str(val))
            writer.writerow(formatted_row)
        return out.getvalue().encode("utf-8")

    def export_csv(self, run_id: str, db: Optional[Session] = None) -> ExportArtifact:
        """Generate a deterministic ZIP archive containing typed CSV datasets for run_id."""
        with self._get_session(db) as session:
            run = session.execute(select(Run).where(Run.id == run_id)).scalar_one_or_none()
            if not run:
                raise RunNotFoundError(run_id)

            plan = session.execute(select(Plan).where(Plan.id == run.plan_id)).scalar_one_or_none()

            # Deterministic candidate ordering: rank ASC (ranked first), candidate_id ASC
            candidates = list(
                session.execute(
                    select(Candidate)
                    .where(Candidate.run_id == run_id)
                    .order_by(Candidate.rank.is_(None), Candidate.rank.asc(), Candidate.id.asc())
                ).scalars().all()
            )

            # Single grouped query for candidate conjunction stats (prevent N+1 queries)
            event_stats_stmt = (
                select(
                    ConjunctionEvent.candidate_id,
                    func.count(ConjunctionEvent.id),
                    func.min(ConjunctionEvent.miss_distance_km),
                )
                .where(ConjunctionEvent.run_id == run_id)
                .group_by(ConjunctionEvent.candidate_id)
            )
            event_stats_rows = session.execute(event_stats_stmt).all()
            event_stats: Dict[str, Tuple[int, Optional[float]]] = {
                str(r[0]): (int(r[1]), float(r[2]) if r[2] is not None else None)
                for r in event_stats_rows
                if r[0] is not None
            }

            # Deterministic event ordering: TCA ASC, miss distance ASC, candidate ASC, debris ASC
            events = list(
                session.execute(
                    select(ConjunctionEvent)
                    .where(ConjunctionEvent.run_id == run_id)
                    .options(joinedload(ConjunctionEvent.debris_object))
                    .order_by(
                        ConjunctionEvent.tca.asc(),
                        ConjunctionEvent.miss_distance_km.asc(),
                        ConjunctionEvent.candidate_id.asc(),
                        ConjunctionEvent.debris_object_id.asc(),
                    )
                ).scalars().all()
            )

            # Latest validation record
            val_rec = session.execute(
                select(ValidationRecord)
                .where(ValidationRecord.run_id == run_id)
                .order_by(desc(ValidationRecord.created_at))
            ).scalars().first()

            now_time = now_utc()

            # 1. plan.csv
            plan_rows: List[List[Any]] = []
            if plan:
                plan_rows.append([
                    plan.id,
                    run.id,
                    plan.created_at,
                    plan.epoch_start,
                    plan.altitude_min_km,
                    plan.altitude_max_km,
                    plan.altitude_step_km,
                    plan.inclination_min_deg,
                    plan.inclination_max_deg,
                    plan.inclination_step_deg,
                    plan.raan_deg,
                    plan.u0_deg,
                    plan.delay_min_minutes,
                    plan.delay_max_minutes,
                    plan.delay_step_minutes,
                    plan.raan_delay_coupling_deg_per_min,
                    plan.screening_days,
                    plan.reference_altitude_km,
                    plan.reference_inclination_deg,
                    plan.dv_budget_m_s,
                    plan.spacecraft_mass_kg,
                    plan.isp_seconds,
                    plan.fuel_weight,
                    plan.risk_weight,
                    plan.data_source,
                    plan.demo_mode,
                    now_time,
                ])
            else:
                plan_rows.append([
                    "",
                    run.id,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    now_time,
                ])

            # 2. candidates.csv
            cand_rows: List[List[Any]] = []
            for c in candidates:
                dep_epoch = None
                if plan and plan.epoch_start is not None:
                    dep_epoch = plan.epoch_start + timedelta(minutes=c.deployment_delay_minutes)

                evt_info = event_stats.get(c.id)
                evt_count = evt_info[0] if evt_info else 0
                min_miss = evt_info[1] if evt_info else None

                cand_rows.append([
                    c.id,
                    c.run_id,
                    c.rank if c.rank is not None else "",
                    c.altitude_km,
                    c.inclination_deg,
                    c.raan_deg,
                    c.u0_deg,
                    c.deployment_delay_minutes,
                    dep_epoch,
                    c.delta_v_m_s,
                    c.propellant_mass_kg,
                    c.fuel_fraction,
                    c.within_dv_budget,
                    c.risk_score,
                    evt_count,
                    min_miss if min_miss is not None else "",
                    "nominal",
                    "",  # composite_score
                ])

            # 3. conjunction_events.csv
            event_rows: List[List[Any]] = []
            for e in events:
                debris_norad = e.debris_object.norad_id if e.debris_object else ""
                event_rows.append([
                    e.id,
                    e.run_id,
                    e.candidate_id or "",
                    e.debris_object_id or "",
                    debris_norad,
                    e.tca,
                    e.miss_distance_km,
                    e.relative_velocity_km_s,
                    e.threshold_km,
                    e.screening_source or "ddato",
                ])

            # Validation CSVs (only when ValidationRecord exists)
            val_summary_bytes: Optional[bytes] = None
            val_matches_bytes: Optional[bytes] = None

            if val_rec is not None:
                val_resp = self.validation_service._record_to_response(val_rec)
                summary_row = [
                    val_resp.validation_id,
                    val_resp.run_id,
                    val_resp.status,
                    val_resp.source,
                    val_resp.source_fetched_at,
                    val_resp.validation_created_at,
                    val_resp.summary.d_dato_event_count,
                    val_resp.summary.external_event_count,
                    val_resp.summary.matched_event_count,
                    val_resp.summary.d_dato_only_count,
                    val_resp.summary.external_only_count,
                    val_resp.summary.external_coverage_percent if val_resp.summary.external_coverage_percent is not None else "",
                    val_resp.summary.d_dato_match_rate_percent if val_resp.summary.d_dato_match_rate_percent is not None else "",
                    val_resp.summary.mean_abs_tca_error_seconds if val_resp.summary.mean_abs_tca_error_seconds is not None else "",
                    val_resp.summary.max_abs_tca_error_seconds if val_resp.summary.max_abs_tca_error_seconds is not None else "",
                    val_resp.summary.mean_abs_miss_distance_difference_km if val_resp.summary.mean_abs_miss_distance_difference_km is not None else "",
                    val_resp.summary.max_abs_miss_distance_difference_km if val_resp.summary.max_abs_miss_distance_difference_km is not None else "",
                ]
                val_summary_bytes = self._serialize_csv(VALIDATION_SUMMARY_HEADERS, [summary_row])

                matches_rows: List[List[Any]] = []
                for m in val_resp.matches:
                    crit_str = (
                        ";".join(m.match_criteria)
                        if isinstance(m.match_criteria, (list, tuple))
                        else str(m.match_criteria or "")
                    )
                    matches_rows.append([
                        m.d_dato_event_id or "",
                        m.external_event_id or "",
                        m.candidate_id or "",
                        m.debris_norad_id or "",
                        m.tca_d_dato,
                        m.tca_external,
                        m.tca_error_seconds if m.tca_error_seconds is not None else "",
                        m.miss_distance_d_dato_km if m.miss_distance_d_dato_km is not None else "",
                        m.miss_distance_external_km if m.miss_distance_external_km is not None else "",
                        m.miss_distance_difference_km if m.miss_distance_difference_km is not None else "",
                        crit_str,
                    ])
                val_matches_bytes = self._serialize_csv(VALIDATION_MATCHES_HEADERS, matches_rows)

            # Assemble ZIP archive with deterministic member ordering
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("plan.csv", self._serialize_csv(PLAN_CSV_HEADERS, plan_rows))
                zf.writestr("candidates.csv", self._serialize_csv(CANDIDATES_CSV_HEADERS, cand_rows))
                zf.writestr("conjunction_events.csv", self._serialize_csv(EVENTS_CSV_HEADERS, event_rows))
                if val_summary_bytes is not None:
                    zf.writestr("validation_summary.csv", val_summary_bytes)
                if val_matches_bytes is not None:
                    zf.writestr("validation_matches.csv", val_matches_bytes)

            zip_bytes = zip_buf.getvalue()
            return ExportArtifact(
                content=zip_bytes,
                media_type="application/zip",
                filename=f"d-dato-{run_id}-export.zip",
            )

    def export_pdf(self, run_id: str, db: Optional[Session] = None) -> ExportArtifact:
        """Generate a deterministic executive screening PDF report for run_id."""
        with self._get_session(db) as session:
            run = session.execute(select(Run).where(Run.id == run_id)).scalar_one_or_none()
            if not run:
                raise RunNotFoundError(run_id)

            plan = session.execute(select(Plan).where(Plan.id == run.plan_id)).scalar_one_or_none()

            # Candidates ordered deterministically: rank ASC, candidate_id ASC
            candidates = list(
                session.execute(
                    select(Candidate)
                    .where(Candidate.run_id == run_id)
                    .order_by(Candidate.rank.is_(None), Candidate.rank.asc(), Candidate.id.asc())
                ).scalars().all()
            )

            # Grouped query for per-candidate event stats
            event_stats_stmt = (
                select(
                    ConjunctionEvent.candidate_id,
                    func.count(ConjunctionEvent.id),
                    func.min(ConjunctionEvent.miss_distance_km),
                )
                .where(ConjunctionEvent.run_id == run_id)
                .group_by(ConjunctionEvent.candidate_id)
            )
            event_stats_rows = session.execute(event_stats_stmt).all()
            event_stats: Dict[str, Tuple[int, Optional[float]]] = {
                str(r[0]): (int(r[1]), float(r[2]) if r[2] is not None else None)
                for r in event_stats_rows
                if r[0] is not None
            }

            # Persisted events ordered deterministically
            events = list(
                session.execute(
                    select(ConjunctionEvent)
                    .where(ConjunctionEvent.run_id == run_id)
                    .options(joinedload(ConjunctionEvent.debris_object))
                    .order_by(
                        ConjunctionEvent.tca.asc(),
                        ConjunctionEvent.miss_distance_km.asc(),
                        ConjunctionEvent.candidate_id.asc(),
                        ConjunctionEvent.debris_object_id.asc(),
                    )
                ).scalars().all()
            )

            # Validation record if present
            val_rec = session.execute(
                select(ValidationRecord)
                .where(ValidationRecord.run_id == run_id)
                .order_by(desc(ValidationRecord.created_at))
            ).scalars().first()

            # Data snapshot if present
            snapshot = None
            if plan:
                snapshot = session.execute(
                    select(DataSnapshot)
                    .where(DataSnapshot.source == plan.data_source)
                    .order_by(desc(DataSnapshot.fetched_at))
                ).scalars().first()

            # Build PDF Document
            buf = io.BytesIO()
            doc = SimpleDocTemplate(
                buf,
                pagesize=letter,
                leftMargin=36,
                rightMargin=36,
                topMargin=48,
                bottomMargin=48,
            )

            styles = getSampleStyleSheet()

            # Custom typography styles
            title_style = ParagraphStyle(
                "DdatoTitle",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                textColor=colors.HexColor("#0F172A"),
            )
            subtitle_style = ParagraphStyle(
                "DdatoSubtitle",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=11,
                leading=15,
                textColor=colors.HexColor("#475569"),
            )
            disclaimer_style = ParagraphStyle(
                "DdatoDisclaimer",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=12,
                textColor=colors.HexColor("#991B1B"),
            )
            sec_heading_style = ParagraphStyle(
                "DdatoSectionHeading",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=12.5,
                leading=16,
                textColor=colors.HexColor("#1E293B"),
                spaceAfter=6,
                keepWithNext=True,
            )
            body_style = ParagraphStyle(
                "DdatoBody",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=12,
                textColor=colors.HexColor("#334155"),
            )
            body_bold = ParagraphStyle(
                "DdatoBodyBold",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=12,
                textColor=colors.HexColor("#1E293B"),
            )
            th_style = ParagraphStyle(
                "DdatoTH",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7.0,
                leading=9.0,
                textColor=colors.white,
                alignment=1,  # Center
            )
            td_style = ParagraphStyle(
                "DdatoTD",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=7.0,
                leading=9.0,
                textColor=colors.HexColor("#1E293B"),
            )
            td_center = ParagraphStyle(
                "DdatoTDCenter",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=7.0,
                leading=9.0,
                textColor=colors.HexColor("#1E293B"),
                alignment=1,
            )
            td_bold = ParagraphStyle(
                "DdatoTDBold",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7.0,
                leading=9.0,
                textColor=colors.HexColor("#1E293B"),
            )

            story: List[Any] = []

            # Document Title & Subtitle
            story.append(Paragraph("D-DATO Screening Report", title_style))
            story.append(Paragraph("Debris-Aware Orbit &amp; Deployment-Window Planner", subtitle_style))
            story.append(Spacer(1, 8))

            # Non-operational Notice Callout Box
            notice_p = Paragraph(NON_OPERATIONAL_DISCLAIMER, disclaimer_style)
            notice_table = Table([[notice_p]], colWidths=[540])
            notice_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
                    ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#DC2626")),
                    ("PADDING", (0, 0), (-1, -1), 8),
                ])
            )
            story.append(notice_table)
            story.append(Spacer(1, 14))

            # SECTION 1 — Run Summary
            story.append(Paragraph("1. Run Summary", sec_heading_style))
            ranked_count = sum(1 for c in candidates if c.rank is not None)
            created_str = format_iso_utc(run.created_at)
            started_str = format_iso_utc(run.started_at) if run.started_at else "N/A"
            completed_str = format_iso_utc(run.completed_at) if run.completed_at else "N/A"

            summary_grid = [
                [
                    Paragraph("Run ID", td_bold),
                    Paragraph(f"<font size=6>{run.id}</font>", td_style),
                    Paragraph("Plan ID", td_bold),
                    Paragraph(f"<font size=6>{run.plan_id}</font>", td_style),
                ],
                [
                    Paragraph("Status", td_bold),
                    Paragraph(f"<b>{run.status.upper()}</b>", td_style),
                    Paragraph("Created At (UTC)", td_bold),
                    Paragraph(created_str, td_style),
                ],
                [
                    Paragraph("Started At (UTC)", td_bold),
                    Paragraph(started_str, td_style),
                    Paragraph("Completed At (UTC)", td_bold),
                    Paragraph(completed_str, td_style),
                ],
                [
                    Paragraph("Candidate Count", td_bold),
                    Paragraph(str(len(candidates)), td_style),
                    Paragraph("Ranked Candidates", td_bold),
                    Paragraph(str(ranked_count), td_style),
                ],
                [
                    Paragraph("Conjunction Events", td_bold),
                    Paragraph(str(len(events)), td_style),
                    Paragraph("Screening Days", td_bold),
                    Paragraph(f"{plan.screening_days} days" if plan else "N/A", td_style),
                ],
            ]
            t_summary = Table(summary_grid, colWidths=[110, 160, 110, 160])
            t_summary.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("PADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ])
            )
            story.append(t_summary)
            story.append(Spacer(1, 14))

            # SECTION 2 — Planning Inputs
            story.append(Paragraph("2. Planning Inputs", sec_heading_style))
            if plan:
                alt_txt = f"{plan.altitude_min_km:.1f} - {plan.altitude_max_km:.1f} km (step {plan.altitude_step_km:.1f} km)"
                inc_txt = f"{plan.inclination_min_deg:.1f} - {plan.inclination_max_deg:.1f}° (step {plan.inclination_step_deg:.1f}°)"
                delay_txt = f"{plan.delay_min_minutes:.0f} - {plan.delay_max_minutes:.0f} min (step {plan.delay_step_minutes:.0f} min)"
                raan_txt = f"{plan.raan_deg:.2f}° (coupling: {plan.raan_delay_coupling_deg_per_min:.5f} °/min)"
                ref_txt = f"{plan.reference_altitude_km:.1f} km, {plan.reference_inclination_deg:.2f}°"
                dv_txt = f"{plan.dv_budget_m_s:.1f} m/s"
                mass_txt = f"{plan.spacecraft_mass_kg:.1f} kg"
                isp_txt = f"{plan.isp_seconds:.1f} s"
                weights_txt = f"Fuel: {plan.fuel_weight:.2f} | Risk: {plan.risk_weight:.2f}"
                source_txt = f"{plan.data_source} ({'Demo Mode' if plan.demo_mode else 'Live'})"

                plan_grid = [
                    [
                        Paragraph("Altitude Envelope", td_bold),
                        Paragraph(alt_txt, td_style),
                        Paragraph("Inclination Envelope", td_bold),
                        Paragraph(inc_txt, td_style),
                    ],
                    [
                        Paragraph("Deployment Delay", td_bold),
                        Paragraph(delay_txt, td_style),
                        Paragraph("RAAN &amp; Delay Coupling", td_bold),
                        Paragraph(raan_txt, td_style),
                    ],
                    [
                        Paragraph("Reference Orbit", td_bold),
                        Paragraph(ref_txt, td_style),
                        Paragraph("Delta-V Budget", td_bold),
                        Paragraph(dv_txt, td_style),
                    ],
                    [
                        Paragraph("Spacecraft Mass", td_bold),
                        Paragraph(mass_txt, td_style),
                        Paragraph("Specific Impulse (Isp)", td_bold),
                        Paragraph(isp_txt, td_style),
                    ],
                    [
                        Paragraph("Objective Weights", td_bold),
                        Paragraph(weights_txt, td_style),
                        Paragraph("Catalog Source", td_bold),
                        Paragraph(source_txt, td_style),
                    ],
                ]
                t_plan = Table(plan_grid, colWidths=[110, 160, 110, 160])
                t_plan.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                        ("PADDING", (0, 0), (-1, -1), 4),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ])
                )
                story.append(t_plan)
            else:
                story.append(Paragraph("Persisted planning inputs unavailable.", body_style))
            story.append(Spacer(1, 14))

            # SECTION 3 — Ranked Candidates
            story.append(Paragraph("3. Ranked Candidates", sec_heading_style))
            if candidates:
                top_candidates = candidates[:20]
                story.append(
                    Paragraph(
                        f"Highest-ranked screening candidates (showing top {len(top_candidates)} of {len(candidates)} evaluated):",
                        body_style,
                    )
                )
                story.append(Spacer(1, 4))

                cand_table_data = [
                    [
                        Paragraph("Rank", th_style),
                        Paragraph("Candidate ID", th_style),
                        Paragraph("Alt (km)", th_style),
                        Paragraph("Inc (°)", th_style),
                        Paragraph("Delay (m)", th_style),
                        Paragraph("ΔV (m/s)", th_style),
                        Paragraph("Fuel Frac", th_style),
                        Paragraph("Risk", th_style),
                        Paragraph("Min Miss (km)", th_style),
                        Paragraph("Events", th_style),
                        Paragraph("Within DV", th_style),
                    ]
                ]

                for c in top_candidates:
                    evt_info = event_stats.get(c.id)
                    evt_cnt = evt_info[0] if evt_info else 0
                    min_m = f"{evt_info[1]:.2f}" if (evt_info and evt_info[1] is not None) else "—"
                    rank_str = str(c.rank) if c.rank is not None else "—"
                    budget_str = "Yes" if c.within_dv_budget else "No"
                    short_id = c.id[:13] + ".." if len(c.id) > 15 else c.id

                    cand_table_data.append([
                        Paragraph(f"<b>{rank_str}</b>", td_center),
                        Paragraph(f"<font size=6>{short_id}</font>", td_style),
                        Paragraph(f"{c.altitude_km:.1f}", td_center),
                        Paragraph(f"{c.inclination_deg:.2f}", td_center),
                        Paragraph(f"{c.deployment_delay_minutes:.0f}", td_center),
                        Paragraph(f"{c.delta_v_m_s:.1f}", td_center),
                        Paragraph(f"{c.fuel_fraction:.4f}", td_center),
                        Paragraph(f"{c.risk_score:.2f}", td_center),
                        Paragraph(min_m, td_center),
                        Paragraph(str(evt_cnt), td_center),
                        Paragraph(budget_str, td_center),
                    ])

                # Total width = 30 + 85 + 46 + 40 + 44 + 46 + 46 + 42 + 55 + 38 + 48 = 520 pt
                t_cand = Table(
                    cand_table_data,
                    colWidths=[30, 85, 46, 40, 44, 46, 46, 42, 57, 36, 48],
                    repeatRows=1,
                )
                t_cand_style = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("PADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
                for r_idx in range(1, len(cand_table_data)):
                    bg = colors.HexColor("#F8FAFC") if r_idx % 2 == 1 else colors.white
                    t_cand_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), bg))
                t_cand.setStyle(TableStyle(t_cand_style))
                story.append(t_cand)
            else:
                story.append(Paragraph("No candidate orbits evaluated.", body_style))
            story.append(Spacer(1, 14))

            # SECTION 4 — Conjunction Events
            story.append(Paragraph("4. Close-Approach Conjunction Events", sec_heading_style))
            if events:
                top_events = events[:20]
                story.append(
                    Paragraph(
                        f"Showing top {len(top_events)} of {len(events)} persisted close-approach events "
                        f"(ordered deterministically by TCA ASC, miss distance ASC):",
                        body_style,
                    )
                )
                story.append(Spacer(1, 4))

                evt_table_data = [
                    [
                        Paragraph("TCA (UTC)", th_style),
                        Paragraph("Candidate ID", th_style),
                        Paragraph("Debris NORAD", th_style),
                        Paragraph("Miss Dist (km)", th_style),
                        Paragraph("Rel Vel (km/s)", th_style),
                        Paragraph("Threshold (km)", th_style),
                    ]
                ]

                for e in top_events:
                    tca_str = format_iso_utc(e.tca)
                    short_cand = (e.candidate_id[:13] + "..") if (e.candidate_id and len(e.candidate_id) > 15) else (e.candidate_id or "—")
                    norad = (e.debris_object.norad_id if e.debris_object else "") or "—"

                    evt_table_data.append([
                        Paragraph(tca_str, td_center),
                        Paragraph(f"<font size=6>{short_cand}</font>", td_style),
                        Paragraph(norad, td_center),
                        Paragraph(f"{e.miss_distance_km:.3f}", td_center),
                        Paragraph(f"{e.relative_velocity_km_s:.2f}", td_center),
                        Paragraph(f"{e.threshold_km:.1f}", td_center),
                    ])

                # Total width = 120 + 95 + 80 + 80 + 85 + 80 = 540 pt
                t_evt = Table(
                    evt_table_data,
                    colWidths=[120, 95, 80, 80, 85, 80],
                    repeatRows=1,
                )
                t_evt_style = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("PADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
                for r_idx in range(1, len(evt_table_data)):
                    bg = colors.HexColor("#F8FAFC") if r_idx % 2 == 1 else colors.white
                    t_evt_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), bg))
                t_evt.setStyle(TableStyle(t_evt_style))
                story.append(t_evt)
            else:
                story.append(
                    Paragraph(
                        "No close-approach conjunction events detected within screening thresholds.",
                        body_style,
                    )
                )
            story.append(Spacer(1, 14))

            # SECTION 5 — Validation (Only when ValidationRecord exists)
            if val_rec is not None:
                story.append(Paragraph("5. External Reference Comparison (SOCRATES)", sec_heading_style))
                val_resp = self.validation_service._record_to_response(val_rec)
                story.append(
                    Paragraph(
                        "Comparative reference metrics against independent external source. "
                        "These metrics represent external reference comparisons and are NOT "
                        "certified flight safety or ground-truth accuracy labels.",
                        body_style,
                    )
                )
                story.append(Spacer(1, 4))

                fetched_str = format_iso_utc(val_resp.source_fetched_at) if val_resp.source_fetched_at else "N/A"
                val_created_str = format_iso_utc(val_resp.validation_created_at)

                cov_str = f"{val_resp.summary.external_coverage_percent:.1f}%" if val_resp.summary.external_coverage_percent is not None else "N/A"
                rate_str = f"{val_resp.summary.d_dato_match_rate_percent:.1f}%" if val_resp.summary.d_dato_match_rate_percent is not None else "N/A"
                mean_tca_str = f"{val_resp.summary.mean_abs_tca_error_seconds:.2f} s" if val_resp.summary.mean_abs_tca_error_seconds is not None else "N/A"
                max_tca_str = f"{val_resp.summary.max_abs_tca_error_seconds:.2f} s" if val_resp.summary.max_abs_tca_error_seconds is not None else "N/A"
                mean_miss_str = f"{val_resp.summary.mean_abs_miss_distance_difference_km:.3f} km" if val_resp.summary.mean_abs_miss_distance_difference_km is not None else "N/A"
                max_miss_str = f"{val_resp.summary.max_abs_miss_distance_difference_km:.3f} km" if val_resp.summary.max_abs_miss_distance_difference_km is not None else "N/A"

                val_grid = [
                    [
                        Paragraph("Validation Source", td_bold),
                        Paragraph(val_resp.source, td_style),
                        Paragraph("Status", td_bold),
                        Paragraph(val_resp.status.upper(), td_style),
                    ],
                    [
                        Paragraph("Reference Snapshot", td_bold),
                        Paragraph(fetched_str, td_style),
                        Paragraph("Comparison Generated", td_bold),
                        Paragraph(val_created_str, td_style),
                    ],
                    [
                        Paragraph("D-DATO Event Count", td_bold),
                        Paragraph(str(val_resp.summary.d_dato_event_count), td_style),
                        Paragraph("External Event Count", td_bold),
                        Paragraph(str(val_resp.summary.external_event_count), td_style),
                    ],
                    [
                        Paragraph("Matched Pairs", td_bold),
                        Paragraph(str(val_resp.summary.matched_event_count), td_style),
                        Paragraph("External Coverage", td_bold),
                        Paragraph(cov_str, td_style),
                    ],
                    [
                        Paragraph("D-DATO Match Rate", td_bold),
                        Paragraph(rate_str, td_style),
                        Paragraph("D-DATO Only Count", td_bold),
                        Paragraph(str(val_resp.summary.d_dato_only_count), td_style),
                    ],
                    [
                        Paragraph("Mean Abs TCA Error", td_bold),
                        Paragraph(mean_tca_str, td_style),
                        Paragraph("Max Abs TCA Error", td_bold),
                        Paragraph(max_tca_str, td_style),
                    ],
                    [
                        Paragraph("Mean Abs Miss Diff", td_bold),
                        Paragraph(mean_miss_str, td_style),
                        Paragraph("Max Abs Miss Diff", td_bold),
                        Paragraph(max_miss_str, td_style),
                    ],
                ]
                t_val = Table(val_grid, colWidths=[120, 150, 120, 150])
                t_val.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                        ("PADDING", (0, 0), (-1, -1), 4),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ])
                )
                story.append(t_val)
                story.append(Spacer(1, 14))

            # SECTION 6 — Data Age and Provenance
            story.append(Paragraph("6. Data Age and Provenance", sec_heading_style))
            snap_time = format_iso_utc(snapshot.fetched_at) if snapshot else "Bundled offline fixture"
            obj_cnt_str = str(snapshot.object_count) if snapshot else "N/A"
            export_time_str = format_iso_utc(now_utc())

            prov_grid = [
                [
                    Paragraph("Data Source", td_bold),
                    Paragraph(plan.data_source if plan else "celestrak", td_style),
                    Paragraph("Execution Mode", td_bold),
                    Paragraph("Offline Demo Fixture" if (plan and plan.demo_mode) else "Live Catalog Feed", td_style),
                ],
                [
                    Paragraph("Snapshot Time (UTC)", td_bold),
                    Paragraph(snap_time, td_style),
                    Paragraph("Tracked Objects in Set", td_bold),
                    Paragraph(obj_cnt_str, td_style),
                ],
                [
                    Paragraph("Export Generated At", td_bold),
                    Paragraph(export_time_str, td_style),
                    Paragraph("Export Engine", td_bold),
                    Paragraph("D-DATO Phase P17 Serialization", td_style),
                ],
            ]
            t_prov = Table(prov_grid, colWidths=[120, 150, 120, 150])
            t_prov.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("PADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ])
            )
            story.append(t_prov)
            story.append(Spacer(1, 14))

            # SECTION 7 — Method and Scope Notes
            story.append(Paragraph("7. Methodological Scope and Limitations", sec_heading_style))
            method_notes = (
                "<b>Circular J2 Candidate Model:</b> Candidate deployment trajectories are evaluated "
                "using circular orbit kinematics coupled with J2 secular nodal precession. Higher-order "
                "gravitational harmonics, atmospheric drag variations, and solar radiation pressure are omitted.<br/><br/>"
                "<b>SGP4 Debris Propagation:</b> Cataloged space debris objects are propagated using standard "
                "SGP4/SDP4 theories from Two-Line Element (TLE) sets, subject to inherent TLE epoch aging.<br/><br/>"
                "<b>Two-Pass Conjunction Screening:</b> A coarse radial bounding box filter eliminates "
                "non-intersecting orbital geometries before fine-grained temporal stepping identifies close-approach events.<br/><br/>"
                "<b>Bounded Heuristic Risk Scoring:</b> Candidates receive a normalized risk score combining "
                "close-approach proximity and event counts. This heuristic score provides comparative screening "
                "differentiation and does NOT calculate collision probability.<br/><br/>"
                "<b>Multi-Objective Ranking:</b> Combines normalized fuel cost and risk score according to "
                "configured user weights.<br/><br/>"
                "<b>Non-Operational Boundary:</b> D-DATO screening results are early-stage mission planning aids. "
                "They do NOT constitute certified flight safety evaluations, operational conjunction assessment, "
                "collision probability calculations, CDM generation, maneuver planning, or launch COLA clearance."
            )
            story.append(Paragraph(method_notes, body_style))

            doc.build(story, canvasmaker=NumberedCanvas)
            pdf_bytes = buf.getvalue()

            return ExportArtifact(
                content=pdf_bytes,
                media_type="application/pdf",
                filename=f"d-dato-{run_id}-report.pdf",
            )


# Singleton provider for FastAPI dependency injection
_export_service_instance: Optional[ExportService] = None


def get_export_service() -> ExportService:
    """Dependency provider returning a singleton ExportService instance."""
    global _export_service_instance
    if _export_service_instance is None:
        _export_service_instance = ExportService()
    return _export_service_instance
