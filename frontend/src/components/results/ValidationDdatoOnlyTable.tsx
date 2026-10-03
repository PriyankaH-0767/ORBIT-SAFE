import React from 'react'
import type { ValidationDdatoOnlyEvent } from '../../types/validation'
import { formatIsoUtc } from '../../utils/date'

export interface ValidationDdatoOnlyTableProps {
  events: ValidationDdatoOnlyEvent[]
  onSelectCandidateId?: (candidateId: string) => void
}

export const ValidationDdatoOnlyTable: React.FC<ValidationDdatoOnlyTableProps> = ({
  events,
  onSelectCandidateId,
}) => {
  if (events.length === 0) {
    return (
      <div className="bg-slate-900/30 border border-slate-800 rounded-xl p-8 text-center text-xs font-mono text-slate-400">
        No D-DATO-only events in this comparison.
      </div>
    )
  }

  return (
    <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden shadow">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <h4 className="text-xs font-semibold text-slate-200 font-mono flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-indigo-400"></span>
          D-DATO-only Events ({events.length})
        </h4>
        <span className="text-[11px] font-mono text-slate-400">
          No matching external reference event within configured tolerances
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 text-[11px]">
            <tr>
              <th className="py-2.5 px-3">Event ID</th>
              <th className="py-2.5 px-3">Candidate</th>
              <th className="py-2.5 px-3">Debris NORAD</th>
              <th className="py-2.5 px-3">TCA (UTC)</th>
              <th className="py-2.5 px-3 text-right">Miss Distance</th>
              <th className="py-2.5 px-3 text-right">Rel. Velocity</th>
              <th className="py-2.5 px-3">Comparison Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-200">
            {events.map((evt, idx) => (
              <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                <td className="py-2.5 px-3 font-medium text-slate-300">
                  {evt.d_dato_event_id.slice(0, 8)}…
                </td>
                <td className="py-2.5 px-3">
                  {evt.candidate_id ? (
                    <button
                      type="button"
                      onClick={() => onSelectCandidateId?.(evt.candidate_id!)}
                      className="text-cyan-400 hover:text-cyan-300 underline font-medium cursor-pointer"
                      title={`Inspect candidate ${evt.candidate_id}`}
                    >
                      {evt.candidate_id.slice(0, 8)}…
                    </button>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="py-2.5 px-3 text-slate-300 font-semibold">
                  {evt.debris_norad_id ? `NORAD ${evt.debris_norad_id}` : '—'}
                </td>
                <td className="py-2.5 px-3 text-slate-300">
                  {evt.tca ? formatIsoUtc(evt.tca) : '—'}
                </td>
                <td className="py-2.5 px-3 text-right text-slate-300">
                  {evt.miss_distance_km != null ? `${evt.miss_distance_km.toFixed(2)} km` : '—'}
                </td>
                <td className="py-2.5 px-3 text-right text-slate-300">
                  {evt.relative_velocity_km_s != null ? `${evt.relative_velocity_km_s.toFixed(2)} km/s` : '—'}
                </td>
                <td className="py-2.5 px-3 text-slate-400 text-[11px] max-w-xs truncate">
                  {evt.notes || 'No matching external reference event within configured tolerances.'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
