import React from 'react'
import { calculateCandidateCount, MAX_CANDIDATES, type CandidateGridParams } from '../../utils/grid'

interface CandidatePreviewProps {
  params: CandidateGridParams
}

export const CandidatePreview: React.FC<CandidatePreviewProps> = ({ params }) => {
  const { count, nAlt, nInc, nDelay, isValid } = calculateCandidateCount(params)
  const isOverLimit = count > MAX_CANDIDATES

  return (
    <div
      className={`p-3 rounded-lg border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5 transition-colors ${
        !isValid
          ? 'bg-slate-900/60 border-slate-800 text-slate-400'
          : isOverLimit
          ? 'bg-rose-950/30 border-rose-800/80 text-rose-200'
          : 'bg-indigo-950/20 border-indigo-800/50 text-indigo-200'
      }`}
    >
      <div className="flex items-center space-x-2">
        <span
          className={`w-2.5 h-2.5 rounded-full ${
            !isValid ? 'bg-slate-500' : isOverLimit ? 'bg-rose-500 animate-pulse' : 'bg-emerald-400'
          }`}
        />
        <span className="text-xs font-semibold tracking-wide uppercase text-slate-300">
          Candidate Grid Preview
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {isValid && (
          <div className="text-[11px] font-mono text-slate-400 flex items-center gap-1.5">
            <span>{nAlt} alt</span>
            <span>×</span>
            <span>{nInc} inc</span>
            <span>×</span>
            <span>{nDelay} delay</span>
          </div>
        )}

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Estimated candidates:</span>
          <span
            className={`font-mono text-sm font-bold px-2 py-0.5 rounded border ${
              !isValid
                ? 'bg-slate-800 border-slate-700 text-slate-400'
                : isOverLimit
                ? 'bg-rose-900/60 border-rose-700 text-rose-300'
                : 'bg-indigo-900/60 border-indigo-700 text-indigo-300'
            }`}
          >
            {count} / {MAX_CANDIDATES}
          </span>
        </div>
      </div>

      {isOverLimit && (
        <div className="w-full text-xs text-rose-400 font-medium pt-1 border-t border-rose-800/40">
          Search space produces {count} candidates, exceeding the backend maximum limit of {MAX_CANDIDATES}. Please increase step sizes or narrow bounds.
        </div>
      )}
    </div>
  )
}
