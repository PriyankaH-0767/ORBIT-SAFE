import React from 'react'

export interface GlobeControlsProps {
  candidateCount: number
  totalCandidates: number
  showDebris: boolean
  onToggleDebris: (show: boolean) => void
  maxDebris: number
  onChangeMaxDebris: (val: number) => void
  sampleStep: number
  onChangeSampleStep: (val: number) => void
  isPlaying: boolean
  onTogglePlay: () => void
  currentUtcTime: string
  playbackSpeed: number
  onChangeSpeed: (speed: number) => void
  onResetView: () => void
  onFocusSelected?: () => void
  hasSelection?: boolean
  disabled?: boolean
}

const SAMPLE_STEP_OPTIONS = [30, 60, 300, 600, 1800, 3600]
const SPEED_OPTIONS = [1, 10, 60, 300]
const DEBRIS_LIMIT_OPTIONS = [5, 10, 25, 50, 100]

export const GlobeControls: React.FC<GlobeControlsProps> = ({
  candidateCount,
  totalCandidates,
  showDebris,
  onToggleDebris,
  maxDebris,
  onChangeMaxDebris,
  sampleStep,
  onChangeSampleStep,
  isPlaying,
  onTogglePlay,
  currentUtcTime,
  playbackSpeed,
  onChangeSpeed,
  onResetView,
  onFocusSelected,
  hasSelection,
  disabled = false,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs font-mono space-y-3">
      {/* Top bar: Playback & Time Sync */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-2.5">
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={onTogglePlay}
            disabled={disabled}
            aria-label={isPlaying ? 'Pause orbital animation' : 'Play orbital animation'}
            className={`px-3 py-1 rounded text-xs font-semibold flex items-center space-x-1.5 transition-colors cursor-pointer ${
              isPlaying
                ? 'bg-amber-600 hover:bg-amber-500 text-white'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <span>{isPlaying ? '⏸ Pause' : '▶ Play'}</span>
          </button>

          <div className="flex items-center space-x-1 text-slate-400">
            <span className="text-[11px]">Speed:</span>
            {SPEED_OPTIONS.map((speed) => (
              <button
                key={speed}
                type="button"
                onClick={() => onChangeSpeed(speed)}
                disabled={disabled}
                className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors cursor-pointer ${
                  playbackSpeed === speed
                    ? 'bg-indigo-600 text-white font-bold'
                    : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                } disabled:opacity-50`}
              >
                {speed}x
              </button>
            ))}
          </div>
        </div>

        {/* Current UTC timestamp */}
        <div className="flex items-center space-x-2 text-slate-300 bg-slate-950 px-2.5 py-1 rounded border border-slate-800">
          <span className="text-slate-400 text-[10px] uppercase tracking-wider">Clock (UTC):</span>
          <span className="font-mono text-cyan-300 font-medium">
            {currentUtcTime || '—'}
          </span>
        </div>
      </div>

      {/* Trajectory & Filtering Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-4">
          {/* Candidates Badge */}
          <div className="flex items-center space-x-1.5 text-slate-300">
            <span className="text-slate-400">Candidates:</span>
            <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-semibold">
              {candidateCount} shown
            </span>
            {totalCandidates > candidateCount && (
              <span className="text-slate-400 text-[11px]">of {totalCandidates}</span>
            )}
          </div>

          {/* Debris Toggle */}
          <label className="flex items-center space-x-2 text-slate-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showDebris}
              onChange={(e) => onToggleDebris(e.target.checked)}
              disabled={disabled}
              className="rounded bg-slate-800 border-slate-700 text-indigo-500 focus:ring-0 cursor-pointer"
            />
            <span>Show debris</span>
          </label>

          {/* Debris Limit Dropdown */}
          {showDebris && (
            <div className="flex items-center space-x-1.5">
              <label htmlFor="debris-limit-select" className="text-slate-400">
                Debris limit:
              </label>
              <select
                id="debris-limit-select"
                value={maxDebris}
                onChange={(e) => onChangeMaxDebris(Number(e.target.value))}
                disabled={disabled}
                className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs focus:outline-none focus:border-indigo-500 cursor-pointer"
              >
                {DEBRIS_LIMIT_OPTIONS.map((val) => (
                  <option key={val} value={val}>
                    {val} objects
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Sampling Dropdown */}
          <div className="flex items-center space-x-1.5">
            <label htmlFor="sample-step-select" className="text-slate-400">
              Sampling:
            </label>
            <select
              id="sample-step-select"
              value={sampleStep}
              onChange={(e) => onChangeSampleStep(Number(e.target.value))}
              disabled={disabled}
              className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs focus:outline-none focus:border-indigo-500 cursor-pointer"
            >
              {SAMPLE_STEP_OPTIONS.map((step) => (
                <option key={step} value={step}>
                  {step >= 60 ? `${step / 60}m` : `${step}s`}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Camera Actions */}
        <div className="flex items-center space-x-2">
          {hasSelection && onFocusSelected && (
            <button
              type="button"
              onClick={onFocusSelected}
              disabled={disabled}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-cyan-300 rounded border border-slate-700 text-xs transition-colors cursor-pointer"
            >
              Focus Selected
            </button>
          )}
          <button
            type="button"
            onClick={onResetView}
            disabled={disabled}
            className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded border border-slate-700 text-xs transition-colors cursor-pointer"
          >
            Reset View
          </button>
        </div>
      </div>
    </div>
  )
}
