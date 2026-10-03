import React from 'react'
import type { CandidateResultItem } from '../../types/candidate'

interface CandidateComparisonProps {
  candidates: CandidateResultItem[]
  onRemoveCandidate: (candidateId: string) => void
  onClear: () => void
  onSelectCandidate?: (candidate: CandidateResultItem) => void
}

export const CandidateComparison: React.FC<CandidateComparisonProps> = ({
  candidates,
  onRemoveCandidate,
  onClear,
  onSelectCandidate,
}) => {
  if (candidates.length === 0) return null

  const rows: { label: string; unit?: string; key: keyof CandidateResultItem | 'fuel_display' | 'budget_display' | 'miss_display' }[] = [
    { label: 'Rank', key: 'rank' },
    { label: 'Altitude', unit: 'km', key: 'altitude_km' },
    { label: 'Inclination', unit: '°', key: 'inclination_deg' },
    { label: 'Deployment Delay', unit: 'min', key: 'deployment_delay_minutes' },
    { label: 'Delta-V Demand', unit: 'm/s', key: 'delta_v_m_s' },
    { label: 'Propellant Mass', unit: 'kg', key: 'propellant_mass_kg' },
    { label: 'Budget Compliance', key: 'budget_display' },
    { label: 'Composite Risk Score', unit: '/ 100', key: 'risk_score' },
    { label: 'Close-Approach Events', key: 'accepted_event_count' },
    { label: 'Minimum Miss Distance', unit: 'km', key: 'miss_display' },
    { label: 'Data Uncertainty', key: 'uncertainty_level' },
  ]

  const formatValue = (cand: CandidateResultItem, key: string, unit?: string): React.ReactNode => {
    switch (key) {
      case 'rank':
        return cand.rank != null ? <span className="font-bold text-cyan-300">Rank #{cand.rank}</span> : '—'
      case 'altitude_km':
        return `${cand.altitude_km.toFixed(1)}${unit ? ` ${unit}` : ''}`
      case 'inclination_deg':
        return `${cand.inclination_deg.toFixed(2)}${unit ? ` ${unit}` : ''}`
      case 'deployment_delay_minutes':
        return `${cand.deployment_delay_minutes.toFixed(1)}${unit ? ` ${unit}` : ''}`
      case 'delta_v_m_s':
        return `${cand.delta_v_m_s.toFixed(2)}${unit ? ` ${unit}` : ''}`
      case 'propellant_mass_kg':
        return `${cand.propellant_mass_kg.toFixed(3)}${unit ? ` ${unit}` : ''}`
      case 'budget_display':
        return (
          <span
            className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border ${
              cand.within_dv_budget
                ? 'bg-emerald-950/70 text-emerald-300 border-emerald-800'
                : 'bg-rose-950/70 text-rose-300 border-rose-800'
            }`}
          >
            {cand.within_dv_budget ? 'Within Budget' : 'Exceeded'}
          </span>
        )
      case 'risk_score':
        return (
          <span className="font-bold text-slate-100">
            {cand.risk_score.toFixed(1)} <span className="text-slate-400 font-normal text-[10px]">/ 100</span>
          </span>
        )
      case 'accepted_event_count':
        return (
          <span className={(cand.accepted_event_count ?? 0) > 0 ? 'text-amber-300 font-bold' : 'text-slate-300'}>
            {cand.accepted_event_count ?? 0}
          </span>
        )
      case 'miss_display':
        return cand.minimum_miss_distance_km != null
          ? `${cand.minimum_miss_distance_km.toFixed(2)} km`
          : '— (No events)'
      case 'uncertainty_level':
        return <span className="capitalize">{cand.uncertainty_level || 'nominal'}</span>
      default:
        return '—'
    }
  }

  const lowestDv = Math.min(...candidates.map((c) => c.delta_v_m_s))
  const lowestRisk = Math.min(...candidates.map((c) => c.risk_score))
  const lowestEvents = Math.min(...candidates.map((c) => c.accepted_event_count ?? 0))

  return (
    <div
      data-testid="candidate-comparison"
      className="p-5 bg-slate-900/90 border border-indigo-500/50 rounded-xl shadow-xl space-y-4 font-mono text-xs"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2.5">
          <span className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse" />
          <h3 className="text-sm font-bold text-white tracking-wide uppercase">
            Candidate Trade-Off Comparison ({candidates.length} / 3 selected)
          </h3>
          <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
            Side-by-Side Analysis
          </span>
        </div>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={onClear}
            className="text-[11px] px-2.5 py-1 text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded border border-slate-700 transition-colors cursor-pointer"
          >
            Clear All
          </button>
        </div>
      </div>

      <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
        Compare candidate configurations using the persisted ranking, propulsion estimates, event counts and screening-risk indicators.
      </p>

      {/* Comparison Grid */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 text-[11px]">
              <th className="py-2.5 pr-4 w-44 font-semibold text-slate-300">Metric / Attribute</th>
              {candidates.map((c) => (
                <th key={c.candidate_id} className="py-2.5 px-3 min-w-44 text-slate-200">
                  <div className="flex items-start justify-between">
                    <div
                      className="cursor-pointer"
                      onClick={() => onSelectCandidate?.(c)}
                      title={`Inspect candidate ${c.candidate_id}`}
                    >
                      <span className="font-bold text-white block hover:text-cyan-300 transition-colors">
                        {c.rank != null ? `Rank #${c.rank}` : 'Candidate'}
                      </span>
                      <span className="text-[10px] text-slate-400 block truncate max-w-[140px]" title={c.candidate_id}>
                        {c.candidate_id.slice(0, 13)}...
                      </span>

                      {/* Part 7: Factual Relative Badges */}
                      {candidates.length >= 2 && (
                        <div className="flex flex-col gap-1 mt-1.5">
                          {c.delta_v_m_s === lowestDv &&
                            candidates.filter((x) => x.delta_v_m_s === lowestDv).length === 1 && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-cyan-950/80 text-cyan-300 border border-cyan-800/80 w-fit">
                                LOWER ESTIMATED ΔV
                              </span>
                            )}
                          {(c.accepted_event_count ?? 0) === lowestEvents &&
                            candidates.filter((x) => (x.accepted_event_count ?? 0) === lowestEvents).length === 1 && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-950/80 text-amber-300 border border-amber-800/80 w-fit">
                                FEWER SCREENED EVENTS
                              </span>
                            )}
                          {c.risk_score === lowestRisk &&
                            candidates.filter((x) => x.risk_score === lowestRisk).length === 1 && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-950/80 text-indigo-300 border border-indigo-800/80 w-fit">
                                LOWER RELATIVE RISK SCORE
                              </span>
                            )}
                        </div>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => onRemoveCandidate(c.candidate_id)}
                      className="text-slate-500 hover:text-rose-400 p-1 text-xs transition-colors cursor-pointer"
                      title="Remove from comparison"
                      aria-label={`Remove candidate ${c.candidate_id} from comparison`}
                    >
                      ✕
                    </button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {rows.map((row) => (
              <tr key={row.label} className="hover:bg-slate-950/40 transition-colors">
                <td className="py-2 pr-4 font-medium text-slate-400 text-[11px]">
                  {row.label}
                </td>
                {candidates.map((c) => (
                  <td key={c.candidate_id} className="py-2 px-3 text-[11px]">
                    {formatValue(c, row.key, row.unit)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded text-[10px] text-slate-400 font-sans italic">
        Note: Relative comparison across candidates within the evaluated screening envelope. Does not constitute an operational flight approval or certified navigation solution.
      </div>
    </div>
  )
}
