import React, { useEffect } from 'react'
import { useAppRoute, navigateTo } from '../../utils/router'

export const Header: React.FC = () => {
  const { route } = useAppRoute()

  useEffect(() => {
    if (route.name === 'results' && route.runId && typeof window !== 'undefined') {
      sessionStorage.setItem('ddato_last_run_id', route.runId)
    }
  }, [route])

  const storedRunId =
    typeof window !== 'undefined' ? sessionStorage.getItem('ddato_last_run_id') : null
  const currentRunId = route.name === 'results' ? route.runId : null
  const lastRunId = currentRunId || storedRunId

  const isPlannerActive = route.name === 'planner'
  const isResultsActive = route.name === 'results'

  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur-md sticky top-0 z-30 shadow-md font-sans">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        {/* Brand & Title */}
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 font-bold tracking-wider text-sm shadow-inner font-mono">
            D
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white font-mono">
                D-DATO
              </h1>
              <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                v0.1.0
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Debris-Aware Orbit & Deployment-Window Planner
            </p>
          </div>
        </div>

        {/* Global Navigation */}
        <nav aria-label="Main Navigation" className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => navigateTo('/')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors cursor-pointer border ${
              isPlannerActive
                ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/50 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border-transparent'
            }`}
          >
            Planner
          </button>

          {isResultsActive ? (
            <span
              className="px-3.5 py-1.5 rounded-lg text-xs font-mono font-medium bg-cyan-600/20 text-cyan-300 border border-cyan-500/50 shadow-sm"
              aria-current="page"
            >
              Results
            </span>
          ) : lastRunId ? (
            <button
              type="button"
              onClick={() => navigateTo(`/results/${encodeURIComponent(lastRunId)}`)}
              className="px-3.5 py-1.5 rounded-lg text-xs font-mono font-medium text-slate-400 hover:text-cyan-300 hover:bg-slate-800/60 transition-colors cursor-pointer border border-transparent"
              title={`View recent run ${lastRunId}`}
            >
              Results
            </button>
          ) : (
            <span
              className="px-3.5 py-1.5 rounded-lg text-xs font-mono text-slate-600 border border-transparent cursor-not-allowed"
              title="No active screening run"
            >
              Results
            </span>
          )}
        </nav>

        {/* Mandatory Non-Operational Scope Disclaimer */}
        <div className="max-w-md text-[11px] text-slate-400 bg-slate-950/70 border border-slate-800/80 rounded-md px-3 py-1.5 leading-relaxed hidden lg:block">
          <span className="font-semibold text-amber-400/90 mr-1.5 font-mono">Note:</span>
          Early-stage screening and planning aid — not an operational collision assessment or maneuver-planning system.
        </div>
      </div>
    </header>
  )
}
