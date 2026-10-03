import React from 'react'

interface ResultsEmptyStateProps {
  title: string
  message: string
  icon?: 'candidates' | 'events'
}

export const ResultsEmptyState: React.FC<ResultsEmptyStateProps> = ({
  title,
  message,
  icon = 'candidates',
}) => {
  return (
    <div className="p-8 text-center bg-slate-900/40 border border-slate-800 rounded-xl space-y-3">
      <div className="w-10 h-10 mx-auto rounded-full bg-slate-800/80 border border-slate-700/60 flex items-center justify-center text-slate-400">
        {icon === 'candidates' ? (
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        )}
      </div>

      <div className="space-y-1">
        <h4 className="text-sm font-semibold text-slate-200 font-mono">{title}</h4>
        <p className="text-xs text-slate-400 max-w-md mx-auto">{message}</p>
      </div>
    </div>
  )
}
