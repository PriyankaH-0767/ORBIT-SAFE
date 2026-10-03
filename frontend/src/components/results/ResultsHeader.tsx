import React from 'react'

interface ResultsHeaderProps {
  runId: string
  planId?: string | null
  status?: string | null
  mode?: string | null
  dataSource?: string | null
  demoMode?: boolean | null
  viewMode?: 'demo' | 'technical' | 'judge'
  onViewModeChange?: (mode: 'demo' | 'technical') => void
  isDemoActive?: boolean
  onToggleDemoMode?: () => void
  onBackToPlanner: () => void
}

export const ResultsHeader: React.FC<ResultsHeaderProps> = ({
  runId,
  planId,
  status = 'completed',
  mode,
  dataSource = 'celestrak',
  demoMode = true,
  viewMode = 'demo',
  onViewModeChange,
  isDemoActive = true,
  onToggleDemoMode,
  onBackToPlanner,
}) => {
  const normalizedStatus = status?.toUpperCase() ?? 'COMPLETED'
  const screeningModeDisplay = demoMode
    ? 'OFFLINE DEMO'
    : mode === 'live'
      ? 'LIVE DATA'
      : 'CACHED DATA'

  return (
    <div className="border-b border-slate-800 pb-5 space-y-3">
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="flex items-center space-x-1.5 text-xs text-slate-400 font-mono">
        <button
          type="button"
          onClick={onBackToPlanner}
          className="hover:text-cyan-400 text-slate-400 transition-colors cursor-pointer"
        >
          D-DATO
        </button>
        <span className="text-slate-600">/</span>
        <span className="text-slate-300">Mission Analysis</span>
        <span className="text-slate-600">/</span>
        <span className="text-cyan-400 font-medium">Run {runId.length > 8 ? runId.slice(0, 8) : runId}</span>
      </nav>

      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white font-mono">
              D-DATO Screening Results
            </h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5" />
              {normalizedStatus}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 font-mono mt-1.5">
            <span>
              Run ID: <span className="text-slate-200 select-all">{runId}</span>
            </span>
            {planId && (
              <span>
                Plan ID: <span className="text-slate-200 select-all">{planId}</span>
              </span>
            )}
            <span
              data-testid="results-screening-mode-indicator"
              className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded bg-slate-950 text-cyan-300 border border-cyan-800/80 text-[10px] font-semibold"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              <span>SCREENING MODE: {screeningModeDisplay}</span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-400">Source: {(dataSource || 'celestrak').toUpperCase()}</span>
              <span className="text-slate-600 hidden sm:inline">•</span>
              <span className="text-slate-400 hidden sm:inline">Frame: TEME • UTC</span>
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start md:self-auto">
          {/* View Mode Toggle: Demo vs Technical (Phase P29.1) */}
          {onViewModeChange && (
            <div
              data-testid="view-mode-selector"
              className="flex items-center p-0.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono"
            >
              <button
                type="button"
                data-testid="toggle-view-demo"
                onClick={() => onViewModeChange('demo')}
                aria-pressed={viewMode === 'demo' || viewMode === 'judge'}
                className={`px-3 py-1 rounded-md font-bold transition-colors cursor-pointer ${
                  viewMode === 'demo' || viewMode === 'judge'
                    ? 'bg-cyan-500 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                DEMO VIEW
              </button>
              <button
                type="button"
                data-testid="toggle-view-technical"
                onClick={() => onViewModeChange('technical')}
                aria-pressed={viewMode === 'technical'}
                className={`px-3 py-1 rounded-md font-bold transition-colors cursor-pointer ${
                  viewMode === 'technical'
                    ? 'bg-cyan-500 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                TECHNICAL VIEW
              </button>
            </div>
          )}

          {/* Optional Demo Mode Toggle */}
          {onToggleDemoMode && (
            <button
              type="button"
              data-testid="toggle-demo-mode"
              onClick={onToggleDemoMode}
              className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono flex items-center gap-1.5 transition-colors cursor-pointer ${
                isDemoActive
                  ? 'bg-cyan-950/80 text-cyan-300 border-cyan-700'
                  : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-white'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isDemoActive ? 'bg-cyan-400 animate-pulse' : 'bg-slate-600'
                }`}
              />
              <span>DEMO MODE: {isDemoActive ? 'ON' : 'OFF'}</span>
            </button>
          )}

          <button
            type="button"
            onClick={onBackToPlanner}
            className="px-3.5 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/80 text-xs font-medium transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
          >
            <span>←</span>
            <span>Back to Planner</span>
          </button>
        </div>
      </div>

      <div className="max-w-3xl text-xs text-slate-400 bg-slate-900/60 border border-slate-800/80 rounded-md px-3 py-1.5 leading-relaxed">
        <span className="font-semibold text-amber-400/90 mr-1.5">Disclaimer:</span>
        Early-stage screening results. Not an operational collision assessment.
      </div>

      {/* Phase P28: Demo Mode provenance banner */}
      {demoMode && (
        <div
          data-testid="demo-mode-provenance-banner"
          className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] font-mono px-3 py-2 rounded-lg bg-cyan-950/30 border border-cyan-800/40"
        >
          <span className="flex items-center gap-1.5 text-cyan-300 font-bold uppercase tracking-wider">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            DEMO MODE
          </span>
          <span className="text-slate-400">
            <span className="text-slate-300 font-semibold">DEMO DATA</span>{' '}
            Deterministic bundled reference run
          </span>
          <span className="text-slate-500">|</span>
          <span className="text-slate-400">
            <span className="text-slate-300 font-semibold">DATA SOURCE</span>{' '}
            CelesTrak Demo Catalog (30 objects, offline)
          </span>
          <span className="text-slate-500">|</span>
          <span className="text-slate-400">
            <span className="text-slate-300 font-semibold">REFERENCE FRAME</span>{' '}
            TEME
          </span>
          <span className="text-slate-500">|</span>
          <span className="text-slate-400">
            <span className="text-slate-300 font-semibold">TIME SCALE</span>{' '}
            UTC
          </span>
        </div>
      )}
    </div>
  )
}
