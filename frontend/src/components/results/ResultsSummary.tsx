import React from 'react'
import type { RunStatusResponse } from '../../types/run'

interface ResultsSummaryProps {
  run: RunStatusResponse | null
  isLoading?: boolean
}

export const ResultsSummary: React.FC<ResultsSummaryProps> = ({ run, isLoading = false }) => {
  if (isLoading && !run) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl animate-pulse">
            <div className="h-3 bg-slate-800 rounded w-24 mb-2" />
            <div className="h-6 bg-slate-800 rounded w-16" />
          </div>
        ))}
      </div>
    )
  }

  const evaluated = run?.candidate_count ?? 0
  const ranked = run?.ranked_candidate_count ?? 0
  const events = run?.conjunction_event_count ?? 0

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div className="p-4 bg-slate-900/80 border border-slate-800/90 rounded-xl shadow-sm">
        <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
          Candidates Evaluated
        </div>
        <div className="text-2xl font-mono font-bold text-white mt-1.5">
          {evaluated.toLocaleString()}
        </div>
        <div className="text-[11px] text-slate-500 font-mono mt-0.5">
          Authoritative backend search grid
        </div>
      </div>

      <div className="p-4 bg-slate-900/80 border border-slate-800/90 rounded-xl shadow-sm">
        <div className="text-[11px] font-mono uppercase tracking-wider text-indigo-400">
          Candidates Ranked
        </div>
        <div className="text-2xl font-mono font-bold text-indigo-300 mt-1.5">
          {ranked.toLocaleString()}
        </div>
        <div className="text-[11px] text-slate-500 font-mono mt-0.5">
          Multi-objective fuel & risk scoring
        </div>
      </div>

      <div className="p-4 bg-slate-900/80 border border-slate-800/90 rounded-xl shadow-sm">
        <div className="text-[11px] font-mono uppercase tracking-wider text-amber-400">
          Conjunction Events
        </div>
        <div className="text-2xl font-mono font-bold text-amber-300 mt-1.5">
          {events.toLocaleString()}
        </div>
        <div className="text-[11px] text-slate-500 font-mono mt-0.5">
          Within 25.0 km screening threshold
        </div>
      </div>
    </div>
  )
}
