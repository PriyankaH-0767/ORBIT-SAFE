import React, { useState } from 'react'
import type { ValidationExecutionRequest } from '../../types/validation'

export interface ValidationControlsProps {
  onRunValidation: (request: ValidationExecutionRequest) => void
  isRunning: boolean
  defaultTcaTolerance?: number
  defaultMissDistanceTolerance?: number
  defaultDemoMode?: boolean
}

export const ValidationControls: React.FC<ValidationControlsProps> = ({
  onRunValidation,
  isRunning,
  defaultTcaTolerance = 300.0,
  defaultMissDistanceTolerance = 5.0,
  defaultDemoMode = true,
}) => {
  const [tcaTolerance, setTcaTolerance] = useState<number>(defaultTcaTolerance)
  const [missTolerance, setMissTolerance] = useState<number>(defaultMissDistanceTolerance)
  const [demoMode, setDemoMode] = useState<boolean>(defaultDemoMode)
  const [formError, setFormError] = useState<string | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (isRunning) return

    if (tcaTolerance <= 0 || Number.isNaN(tcaTolerance)) {
      setFormError('TCA tolerance must be a positive number (> 0 seconds).')
      return
    }

    if (missTolerance <= 0 || Number.isNaN(missTolerance)) {
      setFormError('Miss-distance tolerance must be a positive number (> 0 km).')
      return
    }

    setFormError(null)
    onRunValidation({
      source: 'socrates',
      tca_tolerance_seconds: tcaTolerance,
      miss_distance_tolerance_km: missTolerance,
      demo_mode: demoMode,
    })
  }

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-lg">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4 mb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span>
            External Reference Comparison Configuration
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Compare persisted D-DATO screening conjunction events against an external benchmark dataset.
          </p>
        </div>

        {/* Source Provider Badge */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-mono">Reference Source:</span>
          <span className="px-2.5 py-1 bg-cyan-950/70 border border-cyan-800/80 text-cyan-300 font-mono text-xs rounded-md font-medium">
            SOCRATES (CelesTrak)
          </span>
        </div>
      </div>

      {/* Non-Operational Provenance Notice */}
      <div className="mb-4 bg-slate-950/70 border border-slate-800 rounded-lg p-3 text-xs text-slate-300 font-sans leading-relaxed">
        <span className="font-semibold text-amber-400/90 font-mono uppercase tracking-wider text-[10px] block mb-0.5">
          Provenance & Scope Notice:
        </span>
        Validation compares D-DATO screening events with an external reference dataset. It does not establish operational safety or collision probability.
      </div>

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* TCA Tolerance */}
          <div>
            <label
              htmlFor="tca-tolerance"
              className="block text-xs font-mono text-slate-300 mb-1"
            >
              TCA Tolerance (seconds)
            </label>
            <input
              id="tca-tolerance"
              type="number"
              step="1"
              min="1"
              max="3600"
              value={tcaTolerance}
              onChange={(e) => setTcaTolerance(Number(e.target.value))}
              disabled={isRunning}
              className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
            />
            <span className="text-[10px] text-slate-400 mt-0.5 block">
              Default: 300s (±5 minutes)
            </span>
          </div>

          {/* Miss Distance Tolerance */}
          <div>
            <label
              htmlFor="miss-tolerance"
              className="block text-xs font-mono text-slate-300 mb-1"
            >
              Miss-Distance Tolerance (km)
            </label>
            <input
              id="miss-tolerance"
              type="number"
              step="0.5"
              min="0.1"
              max="100"
              value={missTolerance}
              onChange={(e) => setMissTolerance(Number(e.target.value))}
              disabled={isRunning}
              className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
            />
            <span className="text-[10px] text-slate-400 mt-0.5 block">
              Default: 5.0 km
            </span>
          </div>

          {/* Demo Mode Toggle */}
          <div className="flex flex-col justify-between">
            <span className="block text-xs font-mono text-slate-300 mb-1">
              Execution Environment
            </span>
            <label className="flex items-center gap-2.5 cursor-pointer bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 h-[38px]">
              <input
                type="checkbox"
                checked={demoMode}
                onChange={(e) => setDemoMode(e.target.checked)}
                disabled={isRunning}
                className="w-4 h-4 rounded border-slate-700 text-cyan-500 focus:ring-cyan-500 bg-slate-900 disabled:opacity-50"
              />
              <span className="text-xs font-mono text-slate-200">
                {demoMode ? 'Offline Demo Fixture' : 'Live Source Attempt'}
              </span>
            </label>
            <span className="text-[10px] text-slate-400 mt-0.5 block">
              {demoMode ? 'Self-contained deterministic comparison' : 'Requires external SOCRATES connectivity'}
            </span>
          </div>
        </div>

        {formError && (
          <div className="text-xs text-rose-400 bg-rose-950/40 border border-rose-900/60 rounded px-3 py-1.5 font-mono">
            {formError}
          </div>
        )}

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={isRunning}
            className="px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-mono font-medium rounded-lg shadow transition-colors flex items-center gap-2 cursor-pointer disabled:cursor-not-allowed"
          >
            {isRunning ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/80 border-t-transparent rounded-full animate-spin"></div>
                <span>Validating screening results…</span>
              </>
            ) : (
              <span>Run External Validation</span>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
