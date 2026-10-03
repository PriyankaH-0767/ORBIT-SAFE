import React from 'react'
import { formatIsoUtc } from '../../utils/date'

export interface ValidationProvenanceProps {
  source: string
  status: string
  sourceFetchedAt?: string | null
  validationCreatedAt: string
  validationId: string
}

export const ValidationProvenance: React.FC<ValidationProvenanceProps> = ({
  source,
  status,
  sourceFetchedAt,
  validationCreatedAt,
  validationId,
}) => {
  // Determine provenance classification and distinct visual tokens
  const isDemo = source.toLowerCase().includes('fixture') || source.toLowerCase().includes('demo')
  const isCache = source.toLowerCase().includes('cache')

  let provenanceTitle = 'Live external reference data'
  let badgeStyle = 'bg-emerald-950/80 text-emerald-300 border-emerald-800'
  let containerBorder = 'border-slate-800'

  if (isDemo) {
    provenanceTitle = 'Synthetic demo reference data'
    badgeStyle = 'bg-amber-950/80 text-amber-300 border-amber-800'
    containerBorder = 'border-amber-900/40'
  } else if (isCache) {
    provenanceTitle = 'Cached external reference data'
    badgeStyle = 'bg-blue-950/80 text-blue-300 border-blue-800'
    containerBorder = 'border-blue-900/40'
  }

  return (
    <div className={`bg-slate-900/50 border ${containerBorder} rounded-xl p-4 shadow-md`}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3 mb-3">
        <div className="flex items-center gap-2.5">
          <span className="text-xs text-slate-400 font-mono">Provenance:</span>
          <span className={`px-2.5 py-1 text-xs font-mono font-medium rounded border ${badgeStyle}`}>
            {provenanceTitle}
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
          <span>Status:</span>
          <span
            className={`font-semibold capitalize ${
              status === 'completed' ? 'text-emerald-400' : 'text-slate-200'
            }`}
          >
            {status}
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-[11px] text-slate-500">ID: {validationId.slice(0, 8)}…</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
        <div>
          <span className="text-slate-400 block text-[11px]">Source Key:</span>
          <span className="text-slate-200 font-medium">{source}</span>
        </div>

        <div>
          <span className="text-slate-400 block text-[11px]">Source Snapshot Epoch:</span>
          <span className="text-slate-200">
            {sourceFetchedAt ? formatIsoUtc(sourceFetchedAt) : '—'}
          </span>
        </div>

        <div>
          <span className="text-slate-400 block text-[11px]">Comparison Evaluated (UTC):</span>
          <span className="text-slate-200">{formatIsoUtc(validationCreatedAt)}</span>
        </div>
      </div>
    </div>
  )
}
