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

      {/* 6 Descriptive Comparison Metrics */}
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
    </div>
  )
}
