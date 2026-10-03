import React from 'react'
import type { EventResultItem } from '../../types/event'
import { formatTCAtoUTC } from '../../utils/date'

interface EventTableProps {
  events: EventResultItem[]
  selectedCandidateId?: string | null
  selectedEventId?: string | null
  onSelectEvent?: (event: EventResultItem) => void
  onSelectCandidateId?: (candidateId: string) => void
  isLoading?: boolean
}

export const EventTable: React.FC<EventTableProps> = ({
  events,
  selectedCandidateId,
  selectedEventId,
  onSelectEvent,
  onSelectCandidateId,
  isLoading = false,
}) => {
  if (isLoading && events.length === 0) {
    return (
      <div className="p-8 text-center text-xs font-mono text-slate-400 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2">
        <div className="animate-spin w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full mx-auto" />
        <p>Loading conjunction events…</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800/90 bg-slate-900/80 shadow-sm">
      <table className="w-full text-left border-collapse text-xs font-mono">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400">
            <th className="py-3 px-3.5 font-semibold text-slate-300">TCA (UTC)</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Candidate</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Debris NORAD</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Miss Distance</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Rel Velocity</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Threshold</th>
            <th className="py-3 px-3.5 font-semibold text-slate-300">Source</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60">
          {events.map((evt, idx) => {
            const eventKey = evt.id ?? `evt-${idx}-${evt.tca}`
            const isEventSelected = selectedEventId === (evt.id ?? eventKey)
            const isCandidateMatch =
              selectedCandidateId != null &&
              evt.candidate_id != null &&
              evt.candidate_id === selectedCandidateId

            const noradDisplay = evt.debris_norad_id ?? evt.debris_object_id ?? '—'
            const tcaDisplay = formatTCAtoUTC(evt.tca)

            return (
              <tr
                key={eventKey}
                onClick={() => onSelectEvent?.(evt)}
                className={`transition-colors cursor-pointer ${
                  isEventSelected
                    ? 'bg-amber-950/40 text-white border-l-2 border-amber-500'
                    : isCandidateMatch
                    ? 'bg-indigo-950/30 text-indigo-200 border-l-2 border-indigo-400'
                    : 'hover:bg-slate-800/50 text-slate-300'
                }`}
              >
                <td className="py-2.5 px-3.5 text-slate-200 whitespace-nowrap">
                  {tcaDisplay}
                </td>
                <td className="py-2.5 px-3.5">
                  {evt.candidate_id ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        if (evt.candidate_id && onSelectCandidateId) {
                          onSelectCandidateId(evt.candidate_id)
                        }
                      }}
                      className="bg-slate-800 hover:bg-indigo-900/60 text-slate-200 hover:text-indigo-200 px-1.5 py-0.5 rounded border border-slate-700/60 text-[11px] transition-colors"
                      title="Filter / view candidate"
                    >
                      {evt.candidate_id}
                    </button>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="py-2.5 px-3.5 font-semibold text-amber-400">
                  {noradDisplay}
                </td>
                <td className="py-2.5 px-3.5 font-medium">
                  {evt.miss_distance_km.toFixed(2)} km
                </td>
                <td className="py-2.5 px-3.5">
                  {evt.relative_velocity_km_s.toFixed(2)} km/s
                </td>
                <td className="py-2.5 px-3.5 text-slate-400">
                  {evt.threshold_km.toFixed(1)} km
                </td>
                <td className="py-2.5 px-3.5 text-slate-400 text-[11px]">
                  <span className="bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800">
                    {evt.screening_source}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
