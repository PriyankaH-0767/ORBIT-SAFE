import React from 'react'
import type { HeatmapResponse, HeatmapLayer } from '../../types/heatmap'

interface HeatmapControlsProps {
  heatmapData: HeatmapResponse
  selectedLayer: HeatmapLayer | null
  selectedInclination: number | null
  onSelectInclination: (inclination: number) => void
  isLoading?: boolean
}

export const HeatmapControls: React.FC<HeatmapControlsProps> = ({
  heatmapData,
  selectedLayer,
  selectedInclination,
  onSelectInclination,
  isLoading = false,
}) => {
  const inclinationOptions = heatmapData.inclination_values_deg || []

  // Count populated cells in current layer
  const layerPopulatedCount =
    selectedLayer?.cells?.length ??
    selectedLayer?.values?.flat().filter((v) => v !== null).length ??
    0

  const minRiskDisplay =
    heatmapData.min_risk_score != null ? heatmapData.min_risk_score.toFixed(1) : '—'
  const maxRiskDisplay =
    heatmapData.max_risk_score != null ? heatmapData.max_risk_score.toFixed(1) : '—'

  return (
    <div
      data-testid="heatmap-controls"
      className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3 font-mono text-xs"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        {/* Inclination Slice Dropdown */}
        <div className="flex items-center space-x-2.5">
          <label htmlFor="inclination-select" className="text-slate-300 font-semibold whitespace-nowrap">
            Inclination Slice:
          </label>
          <select
            id="inclination-select"
            aria-label="Inclination Slice"
            value={selectedInclination ?? ''}
            onChange={(e) => onSelectInclination(Number(e.target.value))}
            disabled={isLoading || inclinationOptions.length === 0}
            className="px-2.5 py-1.5 bg-slate-950 border border-slate-700 rounded-md font-mono text-white text-xs focus:outline-none focus:border-indigo-500 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {inclinationOptions.map((inc) => (
              <option key={inc} value={inc}>
                {inc.toFixed(1)}°
              </option>
            ))}
          </select>
        </div>

        {/* Metric and Range info */}
        <div className="text-[11px] text-slate-400">
          <span className="text-slate-300 font-medium">Metric:</span> Screening Risk Score (0–100)
        </div>
      </div>

      {/* Summary Metrics Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-2 border-t border-slate-800/80 text-[11px]">
        <div className="p-2 bg-slate-950/60 rounded border border-slate-800">
          <span className="text-slate-500 block uppercase tracking-wide text-[10px]">
            Selected Slice
          </span>
          <span className="text-white font-bold">
            {selectedInclination != null ? `${selectedInclination.toFixed(1)}°` : '—'}
          </span>
        </div>

        <div className="p-2 bg-slate-950/60 rounded border border-slate-800">
          <span className="text-slate-500 block uppercase tracking-wide text-[10px]">
            Populated Cells
          </span>
          <span className="text-indigo-300 font-bold">
            {layerPopulatedCount.toLocaleString()} / {heatmapData.populated_cells.toLocaleString()}
          </span>
        </div>

        <div className="p-2 bg-slate-950/60 rounded border border-slate-800">
          <span className="text-slate-500 block uppercase tracking-wide text-[10px]">
            Total Candidates
          </span>
          <span className="text-white font-bold">
            {heatmapData.total_candidates.toLocaleString()}
          </span>
        </div>

        <div className="p-2 bg-slate-950/60 rounded border border-slate-800">
          <span className="text-slate-500 block uppercase tracking-wide text-[10px]">
            Min Risk (Run)
          </span>
          <span className="text-emerald-400 font-bold">{minRiskDisplay}</span>
        </div>

        <div className="p-2 bg-slate-950/60 rounded border border-slate-800">
          <span className="text-slate-500 block uppercase tracking-wide text-[10px]">
            Max Risk (Run)
          </span>
          <span className="text-amber-400 font-bold">{maxRiskDisplay}</span>
        </div>
      </div>
    </div>
  )
}
