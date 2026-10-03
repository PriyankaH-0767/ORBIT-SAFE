import React from 'react'
import type { CandidateResultItem } from '../../types/candidate'

interface CandidateTableProps {
  candidates: CandidateResultItem[]
  selectedCandidateId?: string | null
  onSelectCandidate: (candidate: CandidateResultItem) => void
  isLoading?: boolean
}

export const CandidateTable: React.FC<CandidateTableProps> = ({
  candidates,
  selectedCandidateId,
  onSelectCandidate,
  isLoading = false,
}) => {
  if (isLoading && candidates.length === 0) {
    return (
      <div className="p-8 text-center text-xs font-mono text-slate-400 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2">
        <div className="animate-spin w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full mx-auto" />
        <p>Loading ranked candidates…</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800/90 bg-slate-900/80 shadow-sm">
      <table className="w-full text-left border-collapse text-xs font-mono">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400">
            <th className="py-3 px-3.5 font-semibold text-slate-300">Rank</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Candidate ID</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Altitude (km)</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Inclination (°)</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Delay (min)</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Delta-V (m/s)</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Risk Score</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Events</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Min Miss (km)</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Budget</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Uncertainty</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60">
          {candidates.map((cand) => {
            const isSelected = selectedCandidateId === cand.candidate_id
            const displayRank = cand.rank != null ? `Rank ${cand.rank}` : '—'
            const displayMiss =
              cand.minimum_miss_distance_km != null
                ? cand.minimum_miss_distance_km.toFixed(2)
                : '—'
            const eventCount = cand.accepted_event_count ?? 0

            return (
              <tr
                key={cand.candidate_id}
                onClick={() => onSelectCandidate(cand)}
                className={`transition-colors cursor-pointer ${
                  isSelected
                    ? 'bg-indigo-950/40 text-white border-l-2 border-indigo-500'
                    : 'hover:bg-slate-800/50 text-slate-300'
                }`}
              >
                <td className="py-2.5 px-3.5 font-bold text-indigo-400">
                  {displayRank}
                </td>
                <td className="py-2.5 px-3.5 text-slate-200">
                  <span className="bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700/60 text-[11px]">
                    {cand.candidate_id}
                  </span>
                </td>
                <td className="py-2.5 px-3.5">{cand.altitude_km.toFixed(1)}</td>
                <td className="py-2.5 px-3.5">{cand.inclination_deg.toFixed(2)}</td>
                <td className="py-2.5 px-3.5">{cand.deployment_delay_minutes.toFixed(1)}</td>
                <td className="py-2.5 px-3.5">{cand.delta_v_m_s.toFixed(2)}</td>
                <td className="py-2.5 px-3.5 font-semibold">{cand.risk_score.toFixed(1)}</td>
                <td className="py-2.5 px-3.5">
                  <span
                    className={`px-1.5 py-0.5 rounded ${
                      eventCount > 0
                        ? 'bg-amber-950/60 text-amber-300 border border-amber-800/80 font-bold'
                        : 'text-slate-400'
                    }`}
                  >
                    {eventCount}
                  </span>
                </td>
                <td className="py-2.5 px-3.5">{displayMiss}</td>
                <td className="py-2.5 px-3.5">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold border ${
                      cand.within_dv_budget
                        ? 'bg-emerald-950/50 text-emerald-300 border-emerald-800/80'
                        : 'bg-rose-950/50 text-rose-300 border-rose-800/80'
                    }`}
                  >
                    {cand.within_dv_budget ? 'OK' : 'Exceeded'}
                  </span>
                </td>
                <td className="py-2.5 px-3.5 text-slate-400 text-[11px]">
                  {cand.uncertainty_level || 'nominal'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
