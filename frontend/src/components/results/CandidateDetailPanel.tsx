import React from 'react'
import type { CandidateResultItem } from '../../types/candidate'

interface CandidateDetailPanelProps {
  candidate: CandidateResultItem | null
  onClose: () => void
}

export const CandidateDetailPanel: React.FC<CandidateDetailPanelProps> = ({
  candidate,
  onClose,
}) => {
  if (!candidate) return null

  const displayRank = candidate.rank != null ? `Rank ${candidate.rank}` : '—'
  const displayMiss =
    candidate.minimum_miss_distance_km != null
      ? `${candidate.minimum_miss_distance_km.toFixed(2)} km`
      : '—'
  const eventCount = candidate.accepted_event_count ?? 0
  const fuelPct = (candidate.fuel_fraction * 100).toFixed(2)

  return (
    <div
      data-testid="candidate-detail-panel"
      className="p-5 bg-slate-900/90 border border-indigo-500/40 rounded-xl shadow-lg space-y-4 font-mono text-xs text-slate-300"
    >
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-3">
          <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/40 text-sm">
            {displayRank}
          </span>
          <div>
            <h3 className="text-sm font-bold text-white font-mono">
              Candidate: {candidate.candidate_id}
            </h3>
            <p className="text-[11px] text-slate-400">
              Evaluated orbital geometry and screening telemetry
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition-colors"
          aria-label="Close detail panel"
        >
          ✕
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Altitude
          </span>
          <span className="text-white font-bold text-sm">
            {candidate.altitude_km.toFixed(2)} km
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Inclination
          </span>
          <span className="text-white font-bold text-sm">
            {candidate.inclination_deg.toFixed(2)}°
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            RAAN
          </span>
          <span className="text-white font-bold text-sm">
            {candidate.raan_deg.toFixed(2)}°
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Arg of Latitude (u0)
          </span>
          <span className="text-white font-bold text-sm">
            {candidate.u0_deg.toFixed(2)}°
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Deployment Delay
          </span>
          <span className="text-white font-bold text-sm">
            {candidate.deployment_delay_minutes.toFixed(1)} min
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Deployment Epoch
          </span>
          <span className="text-white font-medium text-[11px] truncate block" title={candidate.deployment_epoch ?? '—'}>
            {candidate.deployment_epoch ? candidate.deployment_epoch.replace('T', ' ').replace('Z', ' UTC') : '—'}
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Delta-V
          </span>
          <span className="text-white font-bold text-sm">
            {candidate.delta_v_m_s.toFixed(2)} m/s
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Propellant Mass
          </span>
          <span className="text-white font-bold text-sm">
            {candidate.propellant_mass_kg.toFixed(3)} kg
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Fuel Fraction
          </span>
          <span className="text-white font-bold text-sm">{fuelPct}%</span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Budget Status
          </span>
          <span
            className={`inline-block mt-0.5 px-2 py-0.5 rounded text-[10px] uppercase font-bold border ${
              candidate.within_dv_budget
                ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800'
                : 'bg-rose-950/60 text-rose-300 border-rose-800'
            }`}
          >
            {candidate.within_dv_budget ? 'Within Budget' : 'Budget Exceeded'}
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Risk Score
          </span>
          <span className="text-white font-bold text-sm">
            {candidate.risk_score.toFixed(1)} / 100
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Accepted Events
          </span>
          <span
            className={`font-bold text-sm ${
              eventCount > 0 ? 'text-amber-400' : 'text-slate-300'
            }`}
          >
            {eventCount}
          </span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Min Miss Distance
          </span>
          <span className="text-white font-bold text-sm">{displayMiss}</span>
        </div>

        <div className="p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Uncertainty Level
          </span>
          <span className="text-white font-medium text-xs">
            {candidate.uncertainty_level || 'nominal'}
          </span>
        </div>
      </div>

      {/* Section G: Why is this candidate ranked here? */}
      <div
        data-testid="candidate-why-ranked-panel"
        className="mt-4 p-4 bg-slate-950/90 border border-indigo-500/30 rounded-lg space-y-2.5"
      >
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400" />
          <h4 className="text-xs font-bold text-white font-mono uppercase tracking-wider">
            Why is this candidate ranked here?
          </h4>
        </div>

        <p className="text-xs text-slate-300 font-sans leading-relaxed">
          {candidate.rank != null ? (
            <>
              This candidate is evaluated at <span className="font-semibold text-white font-mono">{candidate.altitude_km.toFixed(1)} km</span> altitude, <span className="font-semibold text-white font-mono">{candidate.inclination_deg.toFixed(2)}°</span> inclination, and a <span className="font-semibold text-white font-mono">{candidate.deployment_delay_minutes.toFixed(1)} min</span> deployment delay. Within the evaluated candidate set, it exhibits a {candidate.risk_score < 30 ? 'relatively low' : candidate.risk_score < 70 ? 'moderate' : 'elevated'} screening-risk score ({candidate.risk_score.toFixed(1)} / 100) and {candidate.within_dv_budget ? 'an estimated propulsion demand within the configured budget' : 'an estimated propulsion demand exceeding the configured budget'} (Delta-V: {candidate.delta_v_m_s.toFixed(2)} m/s, propellant fraction: {fuelPct}%). {eventCount === 0 ? 'No close-approach events were screened within the threshold.' : `${eventCount} close-approach event(s) were screened (minimum miss distance: ${displayMiss}).`}
            </>
          ) : (
            <>
              Candidate evaluated at <span className="font-semibold text-white font-mono">{candidate.altitude_km.toFixed(1)} km</span> and <span className="font-semibold text-white font-mono">{candidate.inclination_deg.toFixed(2)}°</span>. Relative ranking and composite score are determined by multi-objective weights applied to propulsion demand and screening-risk indicators.
            </>
          )}
        </p>

        <div className="pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-400 font-mono">
          <div className="flex items-center space-x-3">
            <span>Rank: <strong className="text-cyan-300">{candidate.rank != null ? `#${candidate.rank}` : '—'}</strong></span>
            <span>Composite Score: <strong className="text-white">{candidate.composite_score != null ? candidate.composite_score.toFixed(3) : '—'}</strong></span>
            <span>Budget: <strong className={candidate.within_dv_budget ? 'text-emerald-400' : 'text-rose-400'}>{candidate.within_dv_budget ? 'Compliant' : 'Exceeded'}</strong></span>
          </div>
          <span className="italic text-slate-500">
            Relative screening heuristic • Non-operational mission planning
          </span>
        </div>
      </div>
    </div>
  )
}
