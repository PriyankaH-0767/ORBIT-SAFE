import React from 'react'
import type { RunStatusResponse } from '../../types/run'
import type { ValidationResponse } from '../../types/validation'
import type { GlobeResponse } from '../../types/globe'

interface DataProvenanceStripProps {
  run: RunStatusResponse | null
  validation?: ValidationResponse | null
  globeData?: GlobeResponse | null
}

export const DataProvenanceStrip: React.FC<DataProvenanceStripProps> = ({
  run,
  validation,
  globeData,
}) => {
  // Sourced from run / validation / globe metadata
  const dataSource = 'CelesTrak (Public LEO Catalog)'
  const executionMode = 'Deterministic Offline Demo Mode'
  const referenceFrame = globeData?.frame ? `${globeData.frame} (True Equator, Mean Equinox)` : 'TEME (Inertial)'
  const timeScale = globeData?.time_scale ? `${globeData.time_scale} (Universal Time Coordinated)` : 'UTC'
  const dataAge = validation?.source_fetched_at
    ? validation.source_fetched_at.replace('T', ' ').replace('Z', ' UTC')
    : run?.created_at
    ? run.created_at.replace('T', ' ').slice(0, 19) + ' UTC'
    : 'Not available'
  const uncertainty = 'Nominal (SGP4 analytical bounds)'

  const items = [
    { label: 'Data Source', value: dataSource, badge: 'PUBLIC' },
    { label: 'Execution Mode', value: executionMode, badge: 'OFFLINE' },
    { label: 'Reference Frame', value: referenceFrame, badge: 'ASTRODYNAMICS' },
    { label: 'Time Scale', value: timeScale, badge: 'TIME' },
    { label: 'Catalog Epoch', value: dataAge, badge: 'SNAPSHOT' },
    { label: 'Uncertainty Model', value: uncertainty, badge: 'BOUNDS' },
  ]

  return (
    <div
      data-testid="data-provenance-strip"
      className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl shadow-sm space-y-2.5 font-mono text-xs"
    >
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400" />
          <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
            Data Provenance & Astrodynamic Integrity Audit Strip
          </span>
        </div>
        <span className="text-[10px] text-slate-400">
          Source of Truth: D-DATO Backend Engine
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
        {items.map((item) => (
          <div
            key={item.label}
            className="p-2.5 bg-slate-900/60 border border-slate-800/70 rounded-lg space-y-1"
          >
            <div className="flex items-center justify-between">
              <span className="text-[9px] uppercase tracking-wider text-slate-400">
                {item.label}
              </span>
              <span className="text-[8px] px-1 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                {item.badge}
              </span>
            </div>
            <div className="text-[11px] font-semibold text-slate-200 truncate" title={item.value}>
              {item.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
