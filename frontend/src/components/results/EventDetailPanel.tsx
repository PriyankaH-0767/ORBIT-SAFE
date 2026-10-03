import React from 'react'
import type { EventResultItem } from '../../types/event'
import { formatTCAtoUTC } from '../../utils/date'

interface EventDetailPanelProps {
  event: EventResultItem | null
  onClose: () => void
}

export const EventDetailPanel: React.FC<EventDetailPanelProps> = ({
  event,
  onClose,
}) => {
  if (!event) return null

  const noradDisplay = event.debris_norad_id ?? event.debris_object_id ?? '—'
  const tcaDisplay = formatTCAtoUTC(event.tca)

  return (
    <div
      data-testid="event-detail-panel"
      className="p-4 bg-slate-900/90 border border-amber-500/40 rounded-xl shadow-lg space-y-3 font-mono text-xs text-slate-300"
    >
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-amber-400" />
          <h4 className="text-sm font-bold text-white font-mono">
            Conjunction Event Details
          </h4>
          {event.id && (
            <span className="text-[11px] text-slate-400">({event.id})</span>
          )}
        </div>

        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition-colors"
          aria-label="Close event detail"
        >
          ✕
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        <div className="p-2 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Candidate ID
          </span>
          <span className="text-white font-bold">{event.candidate_id ?? '—'}</span>
        </div>

        <div className="p-2 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Debris NORAD ID
          </span>
          <span className="text-amber-400 font-bold">{noradDisplay}</span>
        </div>

        <div className="p-2 bg-slate-950/60 rounded border border-slate-800/80 col-span-2">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Time of Closest Approach (TCA)
          </span>
          <span className="text-white font-semibold">{tcaDisplay}</span>
        </div>

        <div className="p-2 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Miss Distance
          </span>
          <span className="text-white font-bold text-sm">
            {event.miss_distance_km.toFixed(2)} km
          </span>
        </div>

        <div className="p-2 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Relative Velocity
          </span>
          <span className="text-white font-bold text-sm">
            {event.relative_velocity_km_s.toFixed(2)} km/s
          </span>
        </div>

        <div className="p-2 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Screening Threshold
          </span>
          <span className="text-white font-semibold">
            {event.threshold_km.toFixed(1)} km
          </span>
        </div>

        <div className="p-2 bg-slate-950/60 rounded border border-slate-800/80">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide block">
            Screening Source
          </span>
          <span className="text-slate-300 font-medium">
            {event.screening_source}
          </span>
        </div>
      </div>
      <p className="text-[10px] text-slate-500 italic">
        Informational event inspection. A future 3D visualization phase will utilize this event geometry.
      </p>
    </div>
  )
}
