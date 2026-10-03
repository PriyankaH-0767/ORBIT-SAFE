import React from 'react'
import type { ValidationSummary } from '../../types/validation'

export interface ValidationSummaryPanelProps {
  summary: ValidationSummary
}

export const ValidationSummaryPanel: React.FC<ValidationSummaryPanelProps> = ({ summary }) => {
  const formatPercent = (val?: number | null) => {
    if (val == null || Number.isNaN(val)) return 'N/A'
    return `${val.toFixed(1)}%`
  }

  const formatSeconds = (val?: number | null) => {
    if (val == null || Number.isNaN(val)) return 'N/A'
    return `${val.toFixed(1)} s`
  }

  const formatKm = (val?: number | null) => {
    if (val == null || Number.isNaN(val)) return 'N/A'
    return `${val.toFixed(3)} km`
  }

  return (
    <div className="space-y-4">
      {/* 5 Event Count Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3.5 shadow">
          <span className="text-[11px] font-mono text-slate-400 block mb-1">D-DATO Events</span>
          <div className="text-xl font-bold font-mono text-cyan-300">
            {summary.d_dato_event_count}
          </div>
          <span className="text-[10px] text-slate-500 block mt-0.5">Primary screening</span>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3.5 shadow">
          <span className="text-[11px] font-mono text-slate-400 block mb-1">External Reference</span>
          <div className="text-xl font-bold font-mono text-slate-200">
            {summary.external_event_count}
          </div>
          <span className="text-[10px] text-slate-500 block mt-0.5">Reported externally</span>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3.5 shadow">
          <span className="text-[11px] font-mono text-slate-400 block mb-1">Matched Events</span>
          <div className="text-xl font-bold font-mono text-emerald-400">
            {summary.matched_event_count}
          </div>
          <span className="text-[10px] text-slate-500 block mt-0.5">Within tolerances</span>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3.5 shadow">
          <span className="text-[11px] font-mono text-slate-400 block mb-1">D-DATO-only</span>
          <div className="text-xl font-bold font-mono text-indigo-300">
            {summary.d_dato_only_count}
          </div>
          <span className="text-[10px] text-slate-500 block mt-0.5">No reference pair</span>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3.5 shadow">
          <span className="text-[11px] font-mono text-slate-400 block mb-1">External-only</span>
          <div className="text-xl font-bold font-mono text-slate-300">
            {summary.external_only_count}
          </div>
          <span className="text-[10px] text-slate-500 block mt-0.5">Outside D-DATO events</span>
        </div>
      </div>

      {/* Section L: Descriptive Comparison Metrics or Zero-Match Explanation */}
      {summary.matched_event_count === 0 ? (
        <div
          data-testid="validation-zero-match-panel"
          className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow space-y-2.5 font-mono"
        >
          <div className="flex flex-wrap items-center gap-2 text-amber-400">
            <span className="px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-xs font-bold font-mono text-amber-300">
              NO MATCHED EVENTS
            </span>
            <h4 className="text-xs font-bold uppercase tracking-wider text-amber-200">
              No event pair satisfied the configured comparison tolerances for this run.
            </h4>
          </div>

          <p className="text-xs text-slate-300 font-sans leading-relaxed">
            Numerical difference metrics are therefore not applicable.
          </p>
          <p className="text-xs text-slate-400 font-sans leading-relaxed">
            This demo produced no paired events suitable for numerical difference metrics.
          </p>
          <p className="sr-only">
            No matching conjunction events were found within the configured comparison tolerances.
          </p>

          <div className="p-3 bg-slate-950/70 rounded-lg border border-slate-800/80 text-[11px] text-slate-400 space-y-1">
            <div className="flex justify-between">
              <span>Primary D-DATO screened events:</span>
              <strong className="text-cyan-300 font-mono">{summary.d_dato_event_count}</strong>
            </div>
            <div className="flex justify-between">
              <span>External reference events:</span>
              <strong className="text-slate-200 font-mono">{summary.external_event_count}</strong>
            </div>
            <div className="flex justify-between">
              <span>Matched event pairs:</span>
              <strong className="text-amber-400 font-mono">0</strong>
            </div>
            <p className="pt-1.5 border-t border-slate-800/60 text-[10px] text-slate-500 font-sans italic">
              Numerical difference metrics (Mean |TCA Error|, Mean |Miss Diff|, Coverage) require spatio-temporally paired conjunctions within the comparison thresholds.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 shadow">
          <h4 className="text-xs font-semibold text-slate-300 font-mono uppercase tracking-wider mb-3">
            Descriptive Comparison Metrics
          </h4>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs font-mono">
            <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3">
              <span className="text-slate-400 text-[11px] block mb-1">External Coverage</span>
              <div className="text-sm font-semibold text-slate-200">
                {formatPercent(summary.external_coverage_percent)}
              </div>
              <span className="text-[9px] text-slate-500">Matched / External</span>
            </div>

            <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3">
              <span className="text-slate-400 text-[11px] block mb-1">D-DATO Match Rate</span>
              <div className="text-sm font-semibold text-slate-200">
                {formatPercent(summary.d_dato_match_rate_percent)}
              </div>
              <span className="text-[9px] text-slate-500">Matched / D-DATO</span>
            </div>

            <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3">
              <span className="text-slate-400 text-[11px] block mb-1">Mean |TCA Error|</span>
              <div className="text-sm font-semibold text-slate-200">
                {formatSeconds(summary.mean_abs_tca_error_seconds)}
              </div>
              <span className="text-[9px] text-slate-500">Average pairing delta</span>
            </div>

            <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3">
              <span className="text-slate-400 text-[11px] block mb-1">Max |TCA Error|</span>
              <div className="text-sm font-semibold text-slate-200">
                {formatSeconds(summary.max_abs_tca_error_seconds)}
              </div>
              <span className="text-[9px] text-slate-500">Maximum pairing delta</span>
            </div>

            <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3">
              <span className="text-slate-400 text-[11px] block mb-1">Mean |Miss Diff|</span>
              <div className="text-sm font-semibold text-slate-200">
                {formatKm(summary.mean_abs_miss_distance_difference_km)}
              </div>
              <span className="text-[9px] text-slate-500">Average distance delta</span>
            </div>

            <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3">
              <span className="text-slate-400 text-[11px] block mb-1">Max |Miss Diff|</span>
              <div className="text-sm font-semibold text-slate-200">
                {formatKm(summary.max_abs_miss_distance_difference_km)}
              </div>
              <span className="text-[9px] text-slate-500">Maximum distance delta</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
