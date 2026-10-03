import React from 'react'
import type { RunStatusResponse } from '../../types/run'
import { navigateTo } from '../../utils/router'

const STAGE_LABELS: Record<string, string> = {
  ingestion: 'Ingesting orbital data',
  candidate_generation: 'Generating candidate deployment windows',
  fuel: 'Estimating delta-v and propellant',
  conjunction_screening: 'Screening close approaches',
  risk: 'Computing screening risk',
  ranking: 'Ranking candidate windows',
  completed: 'Completed',
}

interface RunProgressPanelProps {
  run: RunStatusResponse | null
  runId: string
  planId?: string | null
  isLoading?: boolean
  networkError?: string | null
  onReset: () => void
  onRetry?: () => void
  onViewResults?: (runId: string) => void
}

export const RunProgressPanel: React.FC<RunProgressPanelProps> = ({
  run,
  runId,
  planId,
  isLoading = false,
  networkError = null,
  onReset,
  onViewResults,
}) => {

  const status = run?.status?.toLowerCase() ?? 'queued'
  const isCompleted = status === 'completed'
  const isFailed = status === 'failed' || status === 'cancelled'
  const isRunning = status === 'running' || status === 'queued'

  const progressPercent = Math.min(100, Math.max(0, run?.progress_percent ?? 0))
  const stageKey = run?.current_stage ?? 'queued'
  const stageLabel = STAGE_LABELS[stageKey] || stageKey.replace(/_/g, ' ')

  const statusBadge = () => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5" />
            COMPLETED
          </span>
        )
      case 'failed':
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-rose-500/10 text-rose-400 border border-rose-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-400 mr-1.5" />
            FAILED
          </span>
        )
      case 'cancelled':
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-slate-500/10 text-slate-400 border border-slate-500/30">
            CANCELLED
          </span>
        )
      case 'running':
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mr-1.5 animate-pulse" />
            RUNNING
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5" />
            QUEUED
          </span>
        )
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Network or Polling Error Alert */}
      {networkError && (
        <div className="p-3.5 rounded-lg bg-amber-950/40 border border-amber-800 text-amber-300 text-xs flex items-center justify-between">
          <span>Polling notice: {networkError} (retrying automatically...)</span>
        </div>
      )}

      {/* Main Status Card */}
      <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-800/80 pb-4">
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-semibold text-white font-mono">
                Screening Run
              </h2>
              {statusBadge()}
              {isLoading && (
                <span className="text-slate-500 animate-pulse text-[10px] font-mono">
                  ● syncing
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 font-mono mt-1">
              <span>Run ID: <span className="text-slate-200">{runId}</span></span>
              {planId && <span>Plan ID: <span className="text-slate-200">{planId}</span></span>}
            </div>
          </div>

          <button
            type="button"
            onClick={onReset}
            className="text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 transition-colors border border-slate-700 self-start sm:self-auto cursor-pointer"
          >
            ← Back to Planner
          </button>
        </div>

        {/* Progress Display */}
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400 font-medium">
              Stage: <span className="text-slate-200 font-semibold">{stageLabel}</span>
            </span>
            <span className="font-mono text-indigo-400 font-bold">
              {progressPercent.toFixed(0)}%
            </span>
          </div>

          <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
            <div
              className={`h-2.5 rounded-full transition-all duration-500 ${
                isCompleted
                  ? 'bg-emerald-500'
                  : isFailed
                  ? 'bg-rose-500'
                  : 'bg-indigo-500'
              }`}
              style={{ width: `${progressPercent}%` }}
              role="progressbar"
              aria-valuenow={progressPercent}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>

          {run?.message && (
            <p className="text-xs text-slate-400 font-mono italic">
              &gt; {run.message}
            </p>
          )}
        </div>

        {/* COMPLETED STATE: Summary Counts & Actions */}
        {isCompleted && (
          <div className="pt-4 border-t border-slate-800/80 space-y-5">
            <div className="bg-emerald-950/20 border border-emerald-800/40 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-emerald-400 mb-3 flex items-center gap-2">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Screening Complete
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 bg-slate-900/80 rounded border border-slate-800">
                  <div className="text-[11px] text-slate-400 uppercase tracking-wider font-mono">
                    Candidates Evaluated
                  </div>
                  <div className="text-xl font-mono font-bold text-white mt-1">
                    {run?.candidate_count ?? 0}
                  </div>
                </div>

                <div className="p-3 bg-slate-900/80 rounded border border-slate-800">
                  <div className="text-[11px] text-slate-400 uppercase tracking-wider font-mono">
                    Candidates Ranked
                  </div>
                  <div className="text-xl font-mono font-bold text-indigo-300 mt-1">
                    {run?.ranked_candidate_count ?? 0}
                  </div>
                </div>

                <div className="p-3 bg-slate-900/80 rounded border border-slate-800">
                  <div className="text-[11px] text-slate-400 uppercase tracking-wider font-mono">
                    Conjunction Events
                  </div>
                  <div className="text-xl font-mono font-bold text-amber-300 mt-1">
                    {run?.conjunction_event_count ?? 0}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  if (onViewResults) {
                    onViewResults(runId)
                  } else {
                    navigateTo(`/results/${encodeURIComponent(runId)}`)
                  }
                }}
                className="px-5 py-2 text-xs font-semibold rounded-md bg-indigo-600 hover:bg-indigo-500 text-white transition-colors cursor-pointer shadow-sm"
              >
                View Results
              </button>

              <button
                type="button"
                onClick={onReset}
                className="px-4 py-2 text-xs font-medium rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-slate-700 cursor-pointer"
              >
                Plan Another Mission
              </button>
            </div>
          </div>
        )}

        {/* FAILED STATE */}
        {isFailed && (
          <div className="pt-4 border-t border-slate-800/80 space-y-4">
            <div className="bg-rose-950/20 border border-rose-800/40 rounded-lg p-4 text-rose-300 space-y-2">
              <h3 className="text-sm font-semibold text-rose-400 flex items-center gap-2">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                Screening Execution Failed
              </h3>
              <p className="text-xs text-rose-300 font-mono">
                {run?.error_message || 'The screening pipeline encountered an unrecoverable execution error.'}
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onReset}
                className="px-4 py-2 text-xs font-semibold rounded-md bg-rose-600 hover:bg-rose-500 text-white transition-colors cursor-pointer"
              >
                Modify Parameters & Retry
              </button>
            </div>
          </div>
        )}

        {/* RUNNING / QUEUED STATE HELPER */}
        {isRunning && (
          <div className="text-[11px] text-slate-500 font-mono pt-2">
            Screening is executing asynchronously in the background. Polling for stage updates every 1.2s...
          </div>
        )}
      </div>
    </div>
  )
}
