import React from 'react'

interface ResultsHeaderProps {
  runId: string
  planId?: string | null
  status?: string | null
  onBackToPlanner: () => void
}

export const ResultsHeader: React.FC<ResultsHeaderProps> = ({
  runId,
  planId,
  status = 'completed',
  onBackToPlanner,
}) => {
  const normalizedStatus = status?.toUpperCase() ?? 'COMPLETED'

  return (
    <div className="border-b border-slate-800 pb-5 space-y-3">
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
          </div>
        </div>

        <button
          type="button"
          onClick={onBackToPlanner}
          className="self-start md:self-auto px-3.5 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/80 text-xs font-medium transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
        >
          <span>←</span>
          <span>Back to Planner</span>
        </button>
      </div>

      <div className="max-w-3xl text-xs text-slate-400 bg-slate-900/60 border border-slate-800/80 rounded-md px-3 py-1.5 leading-relaxed">
        <span className="font-semibold text-amber-400/90 mr-1.5">Disclaimer:</span>
        Early-stage screening results. Not an operational collision assessment.
      </div>
    </div>
  )
}
