import React from 'react'
import type { ValidationMatch } from '../../types/validation'

export interface ValidationMatchesTableProps {
  matches: ValidationMatch[]
  onSelectCandidateId?: (candidateId: string) => void
}

export const ValidationMatchesTable: React.FC<ValidationMatchesTableProps> = ({
  matches,
  onSelectCandidateId,
}) => {
  if (matches.length === 0) {
    return (
      <div className="bg-slate-900/30 border border-slate-800 rounded-xl p-8 text-center text-xs font-mono text-slate-400">
        No matched reference events were identified within the configured tolerances.
      </div>
    )
  }

  return (
    <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden shadow">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <h4 className="text-xs font-semibold text-slate-200 font-mono flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          Matched Conjunction Events ({matches.length})
        </h4>
        <span className="text-[11px] font-mono text-slate-400">
          Paired within TCA & miss-distance tolerances
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 text-[11px]">
            <tr>
              <th className="py-2.5 px-3">D-DATO Event</th>
              <th className="py-2.5 px-3">External Event</th>
              <th className="py-2.5 px-3">Candidate</th>
              <th className="py-2.5 px-3">Debris NORAD</th>
              <th className="py-2.5 px-3 text-right">TCA Error</th>
              <th className="py-2.5 px-3 text-right">D-DATO Miss</th>
              <th className="py-2.5 px-3 text-right">External Miss</th>
              <th className="py-2.5 px-3 text-right">Miss Diff</th>
              <th className="py-2.5 px-3">Match Criteria</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-200">
            {matches.map((m, idx) => (
              <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                <td className="py-2.5 px-3 font-medium text-slate-300">
                  {m.d_dato_event_id ? `${m.d_dato_event_id.slice(0, 8)}…` : '—'}
                </td>
                <td className="py-2.5 px-3 text-slate-300">
                  {m.external_event_id || '—'}
                </td>
                <td className="py-2.5 px-3">
                  {m.candidate_id ? (
                    <button
                      type="button"
                      onClick={() => onSelectCandidateId?.(m.candidate_id!)}
                      className="text-cyan-400 hover:text-cyan-300 underline font-medium cursor-pointer"
                      title={`Inspect candidate ${m.candidate_id}`}
                    >
                      {m.candidate_id.slice(0, 8)}…
                    </button>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="py-2.5 px-3 text-slate-300 font-semibold">
                  {m.debris_norad_id ? `NORAD ${m.debris_norad_id}` : '—'}
                </td>
                <td className="py-2.5 px-3 text-right text-slate-300">
                  {m.tca_error_seconds != null ? `${m.tca_error_seconds > 0 ? '+' : ''}${m.tca_error_seconds.toFixed(1)} s` : '—'}
                </td>
                <td className="py-2.5 px-3 text-right text-slate-300">
                  {m.miss_distance_d_dato_km != null ? `${m.miss_distance_d_dato_km.toFixed(2)} km` : '—'}
                </td>
                <td className="py-2.5 px-3 text-right text-slate-300">
                  {m.miss_distance_external_km != null ? `${m.miss_distance_external_km.toFixed(2)} km` : '—'}
                </td>
                <td className="py-2.5 px-3 text-right text-slate-300 font-medium">
                  {m.miss_distance_difference_km != null ? `${m.miss_distance_difference_km > 0 ? '+' : ''}${m.miss_distance_difference_km.toFixed(2)} km` : '—'}
                </td>
                <td className="py-2.5 px-3">
                  <div className="flex flex-wrap gap-1">
                    {m.match_criteria && m.match_criteria.length > 0 ? (
                      m.match_criteria.map((c, i) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 bg-slate-800 text-slate-300 text-[10px] rounded border border-slate-700/80"
                        >
                          {c}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
