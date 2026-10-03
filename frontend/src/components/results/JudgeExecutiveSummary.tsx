import React from 'react'
import type { PlanResponse } from '../../types/plan'
import type { RunStatusResponse } from '../../types/run'
import type { EventResultItem } from '../../types/event'

interface JudgeExecutiveSummaryProps {
  run: RunStatusResponse | null
  plan: PlanResponse | null
  candidateTotal: number
  eventTotal: number
  events?: EventResultItem[]
  isDemoActive?: boolean
}

export const JudgeExecutiveSummary: React.FC<JudgeExecutiveSummaryProps> = ({
  run,
  plan,
  candidateTotal,
  eventTotal,
  events = [],
  isDemoActive = true,
}) => {
  // Compute timeline highlights factually from persisted events
  const timelineStats = React.useMemo(() => {
    if (!events || events.length === 0) return null
    let earliest = events[0].tca
    let latest = events[0].tca
    let minMiss = events[0].miss_distance_km

    for (const e of events) {
      if (e.tca < earliest) earliest = e.tca
      if (e.tca > latest) latest = e.tca
      if (e.miss_distance_km < minMiss) minMiss = e.miss_distance_km
    }

    return {
      earliest,
      latest,
      minMiss,
    }
  }, [events])

  const altitudeRange =
    plan != null
      ? `${plan.altitude_min_km.toFixed(0)}–${plan.altitude_max_km.toFixed(0)} km`
      : '500–600 km'
  const inclinationRange =
    plan != null
      ? `${plan.inclination_min_deg.toFixed(1)}–${plan.inclination_max_deg.toFixed(1)}°`
      : '97.0–98.0°'
  const screeningDays = plan?.screening_days ?? 3.0
  const dataSource = (plan?.data_source || 'celestrak').toUpperCase()

  const workflowSteps = [
    { num: '1', title: 'DEFINE', desc: 'Specify bounded altitude, inclination, and delay grid.' },
    { num: '2', title: 'SCREEN', desc: 'Propagate trajectories and detect close encounters.' },
    { num: '3', title: 'COMPARE', desc: 'Evaluate delta-V demand and screened event counts.' },
    { num: '4', title: 'VISUALIZE', desc: 'Inspect 3D pseudofixed orbits and risk heatmap.' },
    { num: '5', title: 'VALIDATE', desc: 'Benchmark against configured reference catalog.' },
    { num: '6', title: 'EXPORT', desc: 'Generate reproducible CSV datasets and PDF report.' },
  ]

  return (
    <div
      data-testid="demo-executive-summary"
      className="p-5 sm:p-6 bg-slate-900/95 border border-cyan-500/30 rounded-2xl shadow-2xl space-y-6 font-mono text-xs text-slate-300"
    >
      {/* Top Banner: Mode & Mission Identity */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-800 pb-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <h2 className="text-sm sm:text-base font-bold text-white tracking-wider uppercase font-sans">
              DEMO OVERVIEW • D-DATO MISSION SUMMARY
            </h2>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-cyan-950 text-cyan-300 border border-cyan-800">
              SIH 2026 • PS 26209
            </span>
          </div>
          <p className="text-xs text-slate-300 font-sans leading-relaxed">
            D-DATO provides early-stage screening of candidate orbit and deployment configurations using persisted orbital-data and screening results.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="px-2.5 py-1 rounded bg-slate-950 border border-cyan-800/80 text-[11px] text-cyan-300 font-semibold">
            {isDemoActive ? 'OFFLINE DEMO MODE' : 'SCREENING RUN'}
          </span>
        </div>
      </div>

      {/* Part 3: Compact Executive Metrics Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">
            MISSION ENVELOPE
          </span>
          <span className="text-xs font-bold text-cyan-300 block truncate">
            {altitudeRange}
          </span>
          <span className="text-[10px] text-slate-400 block truncate">
            {inclinationRange}
          </span>
        </div>

        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">
            CANDIDATES SCREENED
          </span>
          <span className="text-base font-extrabold text-white block">
            {candidateTotal} <span className="text-xs font-normal text-slate-400">/ 300</span>
          </span>
          <span className="text-[10px] text-emerald-400 block">Evaluated Grid</span>
        </div>

        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">
            CLOSE-APPROACH EVENTS
          </span>
          <span className="text-base font-extrabold text-amber-400 block">
            {eventTotal}
          </span>
          <span className="text-[10px] text-slate-400 block">Threshold: ≤ 25 km</span>
        </div>

        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">
            SCREENING WINDOW
          </span>
          <span className="text-base font-extrabold text-white block">
            {screeningDays.toFixed(1)} <span className="text-xs font-normal text-slate-400">days</span>
          </span>
          <span className="text-[10px] text-slate-400 block">Propagation span</span>
        </div>

        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">
            DATA MODE
          </span>
          <span className="text-xs font-bold text-cyan-300 block truncate">
            {isDemoActive ? 'Offline Demo' : 'Cached / Live'}
          </span>
          <span className="text-[10px] text-slate-400 block truncate">
            {run?.status ? `Status: ${run.status}` : 'Deterministic run'}
          </span>
        </div>

        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">
            DATA SOURCE
          </span>
          <span className="text-xs font-bold text-white block truncate">
            {dataSource}
          </span>
          <span className="text-[10px] text-slate-400 block">Frame: TEME • UTC</span>
        </div>
      </div>

      {/* Part 4 & Part 6: Why D-DATO & Screening Takeaways */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Part 4: Why D-DATO */}
        <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2">
          <div className="flex items-center space-x-2 text-cyan-300 text-xs font-bold uppercase tracking-wider">
            <span>🎯</span>
            <span>WHY D-DATO?</span>
          </div>
          <p className="text-xs text-slate-300 font-sans leading-relaxed">
            Early mission concepts may contain multiple feasible orbit and deployment configurations. D-DATO provides a bounded screening workflow for comparing propulsion demand, close-approach events and relative screening indicators before detailed mission design.
          </p>
          <div className="text-[11px] text-slate-400 font-sans pt-1">
            <span className="text-slate-300 font-bold block mb-1">Key Advantages for CubeSat Mission Planners:</span>
            <ul className="list-disc list-inside space-y-0.5 text-slate-400">
              <li>Evaluates full altitude, inclination &amp; deployment delay combinations</li>
              <li>Calculates J2-coupled delta-V estimates within propellant budgets</li>
              <li>Identifies close approaches against trackable catalog debris</li>
            </ul>
          </div>
        </div>

        {/* Part 6: Key Takeaway Panel */}
        <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2">
          <div className="flex items-center space-x-2 text-amber-300 text-xs font-bold uppercase tracking-wider">
            <span>📊</span>
            <span>SCREENING TAKEAWAYS</span>
          </div>
          <div className="space-y-1.5 text-xs text-slate-300 font-sans">
            <div className="flex items-start space-x-2">
              <span className="text-cyan-400 font-bold">›</span>
              <span><strong>{candidateTotal} candidate configurations</strong> evaluated across the defined search space.</span>
            </div>
            <div className="flex items-start space-x-2">
              <span className="text-cyan-400 font-bold">›</span>
              <span><strong>{eventTotal} screened close-approach events</strong> identified within threshold.</span>
            </div>
            <div className="flex items-start space-x-2">
              <span className="text-cyan-400 font-bold">›</span>
              <span>Candidate results can be compared using delta-v, event count, miss distance and screening-risk indicators.</span>
            </div>
            <div className="flex items-start space-x-2">
              <span className="text-cyan-400 font-bold">›</span>
              <span>3D geometry is available for spatial inspection in the pseudofixed Cesium globe.</span>
            </div>
            <div className="flex items-start space-x-2">
              <span className="text-cyan-400 font-bold">›</span>
              <span>Reference comparison is available using the configured external dataset.</span>
            </div>
          </div>
        </div>
      </div>

      {/* Part 5: How D-DATO Works (Compact Visual Strip) */}
      <div className="space-y-2">
        <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">
          HOW D-DATO WORKS • 6-STAGE ANALYSIS PIPELINE
        </span>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {workflowSteps.map((step) => (
            <div
              key={step.num}
              className="p-2.5 bg-slate-950 border border-slate-800/90 rounded-xl space-y-1"
            >
              <div className="flex items-center space-x-1.5">
                <span className="w-4 h-4 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 text-[10px] font-bold flex items-center justify-center shrink-0">
                  {step.num}
                </span>
                <span className="text-xs font-bold text-white tracking-wider">{step.title}</span>
              </div>
              <p className="text-[10px] text-slate-400 font-sans leading-tight">
                {step.desc}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Part 8: Timeline Highlights Strip (if events exist) */}
      {timelineStats && (
        <div className="p-3 bg-slate-950/70 border border-amber-900/40 rounded-xl flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center space-x-2">
            <span className="text-amber-400 font-bold">⚡ TEMPORAL CONJUNCTION HIGHLIGHTS:</span>
            <span className="text-slate-300">
              Events are shown at their persisted TCA across the screening window.
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[11px]">
            <span>
              Earliest TCA: <strong className="text-white">{timelineStats.earliest.slice(0, 16).replace('T', ' ')} UTC</strong>
            </span>
            <span className="text-slate-600">•</span>
            <span>
              Latest TCA: <strong className="text-white">{timelineStats.latest.slice(0, 16).replace('T', ' ')} UTC</strong>
            </span>
            <span className="text-slate-600">•</span>
            <span>
              Closest Screened Approach: <strong className="text-amber-300">{timelineStats.minMiss.toFixed(2)} km</strong>
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
