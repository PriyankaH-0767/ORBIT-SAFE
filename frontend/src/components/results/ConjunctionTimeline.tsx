import React, { useState, useMemo } from 'react'
import type { EventResultItem } from '../../types/event'
import type { PlanResponse } from '../../types/plan'
import { formatTCAtoUTC } from '../../utils/date'

interface ConjunctionTimelineProps {
  events: EventResultItem[]
  selectedEventId?: string | null
  selectedCandidateId?: string | null
  plan?: PlanResponse | null
  onSelectEvent: (event: EventResultItem) => void
  onInspectInGlobe?: (event: EventResultItem) => void
  onSelectCandidateId?: (candidateId: string) => void
}

type TimelineFilter = 'all' | 'candidate' | 'closest' | 'earliest'

export const ConjunctionTimeline: React.FC<ConjunctionTimelineProps> = ({
  events,
  selectedEventId,
  selectedCandidateId,
  plan,
  onSelectEvent,
  onInspectInGlobe,
  onSelectCandidateId,
}) => {
  const [activeFilter, setActiveFilter] = useState<TimelineFilter>('all')

  // Part 5: Temporal Context - Screening Window bounds
  const epochStartStr = plan?.epoch_start ? formatTCAtoUTC(plan.epoch_start) : 'Run Epoch Start'
  const screeningDays = plan?.screening_days ?? 3.0
  const screeningDurationStr = `${Number(screeningDays).toFixed(1)} Days`

  let epochEndStr = 'Run Epoch End'
  if (plan?.epoch_start) {
    try {
      const startMs = new Date(plan.epoch_start).getTime()
      if (!isNaN(startMs)) {
        const endMs = startMs + screeningDays * 86400000
        epochEndStr = formatTCAtoUTC(new Date(endMs).toISOString())
      }
    } catch {
      // Fallback
    }
  }

  // Part 15: Event Density Summary (display aggregation computed from persisted values)
  const densitySummary = useMemo(() => {
    if (events.length === 0) return null

    let earliestTime = events[0].tca
    let latestTime = events[0].tca
    let minMiss = events[0].miss_distance_km

    for (const evt of events) {
      if (new Date(evt.tca).getTime() < new Date(earliestTime).getTime()) {
        earliestTime = evt.tca
      }
      if (new Date(evt.tca).getTime() > new Date(latestTime).getTime()) {
        latestTime = evt.tca
      }
      if (evt.miss_distance_km < minMiss) {
        minMiss = evt.miss_distance_km
      }
    }

    return {
      total: events.length,
      earliestTca: formatTCAtoUTC(earliestTime),
      latestTca: formatTCAtoUTC(latestTime),
      closestMissKm: minMiss.toFixed(2),
    }
  }, [events])

  // Part 3: Timeline Filtering (client-side presentation logic only)
  const filteredEvents = useMemo(() => {
    let list = [...events]

    if (activeFilter === 'candidate' && selectedCandidateId) {
      list = list.filter((e) => e.candidate_id === selectedCandidateId)
    } else if (activeFilter === 'closest') {
      list.sort((a, b) => a.miss_distance_km - b.miss_distance_km)
    } else if (activeFilter === 'earliest') {
      list.sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime())
    } else {
      // Default: chronological by TCA
      list.sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime())
    }

    return list
  }, [events, activeFilter, selectedCandidateId])

  // Part 4: Empty Timeline Display
  if (events.length === 0) {
    return (
      <div
        data-testid="conjunction-timeline-empty"
        className="p-6 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3 font-mono text-center"
      >
        <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 text-slate-400 flex items-center justify-center mx-auto text-lg">
          ⏱
        </div>
        <h4 className="text-sm font-bold text-white tracking-wide uppercase">
          NO SCREENED CLOSE-APPROACH EVENTS
        </h4>
        <p className="text-xs text-slate-400 max-w-lg mx-auto font-sans leading-relaxed">
          No conjunction events were identified within the configured screening threshold and time window.
        </p>
      </div>
    )
  }

  return (
    <div
      data-testid="conjunction-timeline"
      className="p-5 bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl space-y-5 font-mono"
    >
      {/* Header & Temporal Context */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
            <h3 className="text-sm font-bold text-white tracking-wide uppercase">
              CONJUNCTION TIMELINE
            </h3>
            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
              Temporal Screening Dispersion
            </span>
          </div>
          <p className="text-xs text-slate-400 font-sans mt-0.5">
            Markers indicate screened close-approach events at their persisted TCA across the screening window.
          </p>
        </div>

        {/* Part 5: Temporal Context Box */}
        <div className="flex flex-wrap items-center gap-2 text-xs bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2">
          <div className="flex flex-col">
            <span className="text-[9px] text-slate-500 uppercase font-bold">Screening Window Start</span>
            <span className="text-slate-200 text-[11px]">{epochStartStr}</span>
          </div>
          <span className="text-slate-700 hidden sm:inline">→</span>
          <div className="flex flex-col">
            <span className="text-[9px] text-slate-500 uppercase font-bold">Screening Window End</span>
            <span className="text-slate-200 text-[11px]">{epochEndStr}</span>
          </div>
          <div className="pl-2 border-l border-slate-800 flex flex-col">
            <span className="text-[9px] text-slate-500 uppercase font-bold">Duration</span>
            <span className="text-cyan-300 font-bold text-[11px]">{screeningDurationStr}</span>
          </div>
        </div>
      </div>

      {/* Part 15: Event Density Summary Cards */}
      {densitySummary && (
        <div
          data-testid="event-density-summary"
          className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs"
        >
          <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-2.5">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Events Screened</span>
            <span className="text-base font-bold text-white mt-0.5 block">{densitySummary.total}</span>
            <span className="text-[9px] text-slate-500 block">within threshold ≤ 25.0 km</span>
          </div>
          <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-2.5">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Earliest TCA</span>
            <span className="text-xs font-semibold text-slate-200 mt-1 block truncate" title={`Earliest: ${densitySummary.earliestTca}`}>
              {`Earliest: ${densitySummary.earliestTca}`}
            </span>
            <span className="text-[9px] text-slate-500 block">UTC screening baseline</span>
          </div>
          <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-2.5">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Latest TCA</span>
            <span className="text-xs font-semibold text-slate-200 mt-1 block truncate" title={`Latest: ${densitySummary.latestTca}`}>
              {`Latest: ${densitySummary.latestTca}`}
            </span>
            <span className="text-[9px] text-slate-500 block">UTC screening window</span>
          </div>
          <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-2.5">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Closest Screened Miss</span>
            <span className="text-base font-bold text-amber-300 mt-0.5 block">
              {densitySummary.closestMissKm} <span className="text-xs font-normal text-slate-400">km</span>
            </span>
            <span className="text-[9px] text-slate-500 block">minimum spatial separation</span>
          </div>
        </div>
      )}

      {/* Part 3: Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-slate-800/80">
        <div className="flex items-center space-x-1.5 text-xs">
          <span className="text-slate-400 text-[11px] uppercase mr-1">Filter Events:</span>
          <button
            type="button"
            onClick={() => setActiveFilter('all')}
            className={`px-2.5 py-1 rounded text-xs transition-colors cursor-pointer border ${
              activeFilter === 'all'
                ? 'bg-amber-950 text-amber-300 border-amber-700 font-bold'
                : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
            }`}
          >
            All Events ({events.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveFilter('candidate')}
            disabled={!selectedCandidateId}
            title={selectedCandidateId ? `Filter by candidate ${selectedCandidateId}` : 'Select a candidate in the table first'}
            className={`px-2.5 py-1 rounded text-xs transition-colors cursor-pointer border disabled:opacity-40 disabled:cursor-not-allowed ${
              activeFilter === 'candidate'
                ? 'bg-cyan-950 text-cyan-300 border-cyan-700 font-bold'
                : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
            }`}
          >
            Selected Candidate {selectedCandidateId ? `(${selectedCandidateId.slice(0, 8)}…)` : ''}
          </button>
          <button
            type="button"
            onClick={() => setActiveFilter('closest')}
            className={`px-2.5 py-1 rounded text-xs transition-colors cursor-pointer border ${
              activeFilter === 'closest'
                ? 'bg-amber-950 text-amber-300 border-amber-700 font-bold'
                : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
            }`}
          >
            Closest Miss Distance
          </button>
          <button
            type="button"
            onClick={() => setActiveFilter('earliest')}
            className={`px-2.5 py-1 rounded text-xs transition-colors cursor-pointer border ${
              activeFilter === 'earliest'
                ? 'bg-indigo-950 text-indigo-300 border-indigo-700 font-bold'
                : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
            }`}
          >
            Earliest Events
          </button>
        </div>

        <span className="text-[10px] text-slate-500 font-sans italic">
          Showing {filteredEvents.length} of {events.length} screened events • Click an event to inspect
        </span>
      </div>

      {/* Part 1 & 16: Chronological Spine Timeline */}
      <div className="relative pl-6 sm:pl-8 border-l-2 border-slate-800 space-y-3.5 my-2">
        {/* Timeline Start Marker */}
        <div className="relative -left-[31px] sm:-left-[39px] flex items-center space-x-2 text-[10px] text-slate-500">
          <span className="w-3 h-3 rounded-full bg-slate-800 border-2 border-slate-600 shrink-0" />
          <span className="uppercase tracking-wider font-semibold">Screening Window Start:</span>
          <span className="text-slate-400">{epochStartStr}</span>
        </div>

        {/* Event Nodes */}
        {filteredEvents.map((evt, idx) => {
          const isSelected = selectedEventId === (evt.id ?? `evt-${idx}`)
          const isCandidateMatched = selectedCandidateId != null && evt.candidate_id === selectedCandidateId
          const tcaUtc = formatTCAtoUTC(evt.tca)

          return (
            <div
              key={evt.id ?? `evt-${idx}`}
              tabIndex={0}
              role="button"
              aria-label={`Conjunction event TCA ${tcaUtc}, miss distance ${evt.miss_distance_km.toFixed(2)} km, debris NORAD ${evt.debris_norad_id ?? 'unknown'}`}
              onClick={() => onSelectEvent(evt)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelectEvent(evt)
                }
              }}
              className={`relative -left-[31px] sm:-left-[39px] flex items-start space-x-3 p-3 rounded-xl border transition-all cursor-pointer outline-none focus:ring-2 focus:ring-amber-400 ${
                isSelected
                  ? 'bg-amber-950/40 border-amber-500 shadow-lg ring-1 ring-amber-500/50'
                  : isCandidateMatched
                    ? 'bg-cyan-950/30 border-cyan-800/80 hover:border-cyan-600'
                    : 'bg-slate-950/80 border-slate-800/90 hover:border-slate-700'
              }`}
            >
              {/* Spine Node Marker */}
              <div
                className={`w-3.5 h-3.5 rounded-full mt-1 shrink-0 flex items-center justify-center border-2 transition-all ${
                  isSelected
                    ? 'bg-amber-400 border-white ring-4 ring-amber-500/30'
                    : isCandidateMatched
                      ? 'bg-cyan-400 border-cyan-200'
                      : 'bg-slate-800 border-amber-500/60'
                }`}
              >
                {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
              </div>

              {/* Event Content Card */}
              <div className="flex-1 min-w-0 space-y-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold text-white tracking-tight">
                      {`TCA • ${tcaUtc}`}
                    </span>
                    {isSelected && (
                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-900/80 text-amber-200 border border-amber-700 uppercase font-semibold">
                        Selected Event
                      </span>
                    )}
                    {isCandidateMatched && !isSelected && (
                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 uppercase font-semibold">
                        Matched Candidate
                      </span>
                    )}
                  </div>

                  <div className="flex items-center space-x-2 text-xs">
                    <span className="text-slate-400 text-[10px]">Miss Distance:</span>
                    <span className="text-amber-300 font-bold">
                      {evt.miss_distance_km.toFixed(2)} km
                    </span>
                  </div>
                </div>

                {/* Telemetry Detail Line */}
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-300">
                  <div>
                    <span className="text-slate-500 mr-1">Debris:</span>
                    <span className="text-slate-200 font-semibold">
                      NORAD #{evt.debris_norad_id ?? evt.debris_object_id ?? 'Unknown'}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-500 mr-1">Candidate:</span>
                    <span
                      onClick={(e) => {
                        e.stopPropagation()
                        if (evt.candidate_id && onSelectCandidateId) {
                          onSelectCandidateId(evt.candidate_id)
                        }
                      }}
                      className="text-cyan-300 hover:underline cursor-pointer truncate max-w-[130px] inline-block align-bottom"
                      title={evt.candidate_id ?? ''}
                    >
                      {evt.candidate_id ? `${evt.candidate_id.slice(0, 10)}…` : '—'}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-500 mr-1">Rel Velocity:</span>
                    <span className="text-slate-300">{evt.relative_velocity_km_s.toFixed(2)} km/s</span>
                  </div>

                  <div>
                    <span className="text-slate-500 mr-1">Threshold:</span>
                    <span className="text-slate-400">≤ {evt.threshold_km.toFixed(1)} km</span>
                  </div>
                </div>

                {/* Inline Action on Selection */}
                {isSelected && onInspectInGlobe && (
                  <div className="pt-2 flex items-center justify-between border-t border-amber-900/40">
                    <span className="text-[10px] text-amber-200/80 font-sans">
                      Event selected • Conjunction coordinates loaded in 3D scene
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        onInspectInGlobe(evt)
                      }}
                      className="px-2.5 py-1 text-[11px] font-bold rounded bg-amber-500 hover:bg-amber-400 text-slate-950 transition-colors cursor-pointer flex items-center space-x-1"
                    >
                      <span>Inspect spatial geometry in 3D Globe ↓</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          )
        })}

        {/* Timeline End Marker */}
        <div className="relative -left-[31px] sm:-left-[39px] flex items-center space-x-2 text-[10px] text-slate-500 pt-1">
          <span className="w-3 h-3 rounded-full bg-slate-800 border-2 border-slate-600 shrink-0" />
          <span className="uppercase tracking-wider font-semibold">Screening Window End:</span>
          <span className="text-slate-400">{epochEndStr}</span>
        </div>
      </div>

      {/* Footer Disclaimer */}
      <div className="text-[10px] text-slate-500 font-sans border-t border-slate-800 pt-2">
        Note: Conjunction timeline markers represent temporal points of closest approach (TCA) identified by SGP4 propagation against the debris catalog. It does not calculate collision probability or operational maneuver approval.
      </div>
    </div>
  )
}
