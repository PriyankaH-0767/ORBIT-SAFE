import React from 'react'
import type { RunStatusResponse } from '../../types/run'

interface ResultsSummaryProps {
  run: RunStatusResponse | null
  isLoading?: boolean
}

export const ResultsSummary: React.FC<ResultsSummaryProps> = ({ run, isLoading = false }) => {
  if (isLoading && !run) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="p-3.5 bg-slate-900/60 border border-slate-800 rounded-xl animate-pulse">
            <div className="h-3 bg-slate-800 rounded w-20 mb-2" />
            <div className="h-6 bg-slate-800 rounded w-16" />
          </div>
        ))}
      </div>
    )
  }

  const evaluated = run?.candidate_count ?? 0
  const ranked = run?.ranked_candidate_count ?? 0
  const events = run?.conjunction_event_count ?? 0
  const status = run?.status ? run.status.toUpperCase() : 'COMPLETED'
  const dataSource = 'CelesTrak (Public LEO)'
  const dataMode = 'Offline Demo Mode'
  const screeningDuration = '3 Days'

  return (
    <div
      data-testid="results-mission-outcome"
      className="p-5 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-xl space-y-4 font-mono text-xs text-slate-300"
    >
      {/* Top Header Strip */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2.5">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
          <h2 className="text-sm font-bold text-white tracking-wide uppercase font-mono">
            Mission Screening Outcome & Search Envelope Summary
          </h2>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider">Run Status:</span>
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
              status === 'COMPLETED'
                ? 'bg-emerald-950/70 text-emerald-300 border-emerald-800'
                : 'bg-indigo-950/70 text-indigo-300 border-indigo-800'
            }`}
          >
            {status}
          </span>
        </div>
      </div>

      {/* Explanatory Context */}
      <p className="text-xs text-slate-300 font-sans leading-relaxed">
        This dashboard summarizes a screening analysis of the selected mission search space. Results evaluate relative trade-offs between estimated propulsion demand and close-approach debris proximity across the candidate grid.
      </p>

      {/* 6 Key Mission Outcome Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-3 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
            Candidates Screened
          </span>
          <div className="text-xl font-bold font-mono text-white">
            {evaluated.toLocaleString()}
          </div>
          <span className="text-[10px] text-slate-500 block truncate">Search space grid</span>
        </div>

        <div className="p-3 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-cyan-400 block">
            Candidates Ranked
          </span>
          <div className="text-xl font-bold font-mono text-cyan-300">
            {ranked.toLocaleString()}
          </div>
          <span className="text-[10px] text-slate-500 block truncate">Multi-objective Pareto</span>
        </div>

        <div className="p-3 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-amber-400 block">
            Close Approaches
          </span>
          <div className="text-xl font-bold font-mono text-amber-300">
            {events.toLocaleString()}
          </div>
          <span className="text-[10px] text-slate-500 block truncate">Threshold &le; 25.0 km</span>
        </div>

        <div className="p-3 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
            Catalog Source
          </span>
          <div className="text-xs font-semibold font-mono text-slate-200 truncate" title={dataSource}>
            {dataSource}
          </div>
          <span className="text-[10px] text-slate-500 block truncate">Ephemeris baseline</span>
        </div>

        <div className="p-3 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
            Execution Mode
          </span>
          <div className="text-xs font-semibold font-mono text-slate-200 truncate" title={dataMode}>
            {dataMode}
          </div>
          <span className="text-[10px] text-slate-500 block truncate">Deterministic run</span>
        </div>

        <div className="p-3 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
            Screening Window
          </span>
          <div className="text-xs font-semibold font-mono text-slate-200 truncate">
            {screeningDuration}
          </div>
          <span className="text-[10px] text-slate-500 block truncate">SGP4 propagation</span>
        </div>
      </div>

      {/* Non-Operational Reminder Footnote */}
      <div className="text-[10px] text-slate-500 italic pt-1 border-t border-slate-800/60">
        Non-operational screening indicator. Results reflect heuristic filtering within the user-specified envelope; not certified collision probability or flight maneuver approval.
      </div>
    </div>
  )
}
