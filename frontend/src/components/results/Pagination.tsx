import React from 'react'

interface PaginationProps {
  total: number
  limit: number
  offset: number
  onPageChange: (newOffset: number) => void
  disabled?: boolean
  label?: string
}

export const Pagination: React.FC<PaginationProps> = ({
  total,
  limit,
  offset,
  onPageChange,
  disabled = false,
  label = 'records',
}) => {
  if (total <= 0) return null

  const start = Math.min(total, offset + 1)
  const end = Math.min(total, offset + limit)
  const canPrev = offset > 0 && !disabled
  const canNext = offset + limit < total && !disabled

  const handlePrev = () => {
    if (canPrev) {
      onPageChange(Math.max(0, offset - limit))
    }
  }

  const handleNext = () => {
    if (canNext) {
      onPageChange(offset + limit)
    }
  }

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 py-3 px-4 bg-slate-900/60 border border-slate-800 rounded-lg text-xs font-mono text-slate-400">
      <div>
        Showing <span className="text-slate-200 font-semibold">{start}</span>–
        <span className="text-slate-200 font-semibold">{end}</span> of{' '}
        <span className="text-slate-200 font-semibold">{total.toLocaleString()}</span> {label}
      </div>

      <div className="flex items-center space-x-2">
        <button
          type="button"
          onClick={handlePrev}
          disabled={!canPrev}
          className={`px-3 py-1.5 rounded border text-xs transition-colors ${
            canPrev
              ? 'bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 cursor-pointer'
              : 'bg-slate-900 text-slate-600 border-slate-800/80 cursor-not-allowed opacity-60'
          }`}
        >
          ← Previous
        </button>

        <button
          type="button"
          onClick={handleNext}
          disabled={!canNext}
          className={`px-3 py-1.5 rounded border text-xs transition-colors ${
            canNext
              ? 'bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 cursor-pointer'
              : 'bg-slate-900 text-slate-600 border-slate-800/80 cursor-not-allowed opacity-60'
          }`}
        >
          Next →
        </button>
      </div>
    </div>
  )
}
