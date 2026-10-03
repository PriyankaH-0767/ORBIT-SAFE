import React from 'react'
import { MISSION_PRESETS, type MissionPreset } from '../../types/presets'

interface MissionPresetsProps {
  activePresetId: string
  onSelectPreset: (preset: MissionPreset) => void
  onTryDemo: () => void
  disabled?: boolean
  isDemoLoading?: boolean
}

export const MissionPresets: React.FC<MissionPresetsProps> = ({
  activePresetId,
  onSelectPreset,
  onTryDemo,
  disabled = false,
  isDemoLoading = false,
}) => {
  return (
    <div
      data-testid="mission-presets"
      className="p-5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-4 font-mono"
    >
      {/* Top Banner: Quick Action for Guided Demo */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-gradient-to-r from-cyan-950/60 via-slate-900 to-indigo-950/60 p-3.5 rounded-lg border border-cyan-800/40">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs uppercase font-bold tracking-wider text-cyan-300">
              ⚡ Guided Demo Mode
            </span>
            <span className="px-1.5 py-0.5 rounded text-[10px] bg-cyan-900/60 text-cyan-200 border border-cyan-700">
              {isDemoLoading ? 'LOADING DEMO…' : 'INSTANT DEMO'}
            </span>
          </div>
          <p className="text-xs text-slate-300 font-sans mt-0.5">
            Opens the pre-computed deterministic demo run instantly — no 90-second recomputation required.
          </p>
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          <button
            type="button"
            onClick={onTryDemo ?? (() => onSelectPreset(MISSION_PRESETS[0]))}
            disabled={disabled}
            aria-label="Start Guided Demo — Try 2-Minute Demo (~90s Screening Run)"
            data-testid="open-guided-demo-btn"
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold text-xs rounded-lg shadow-md hover:shadow-cyan-500/20 transition-all cursor-pointer flex items-center space-x-1.5 disabled:opacity-50"
          >
            {isDemoLoading ? (
              <>
                <span className="w-3 h-3 border-2 border-slate-900 border-t-transparent rounded-full animate-spin" aria-hidden="true" />
                <span>LOADING DEMO…</span>
              </>
            ) : (
              <div className="flex flex-col items-center leading-tight">
                <span>🚀 START GUIDED DEMO</span>
                <span className="text-[9px] font-medium text-slate-950/80">~90s Screening Run</span>
              </div>
            )}
          </button>
          <button
            type="button"
            onClick={() => {
              const custom = MISSION_PRESETS.find((p) => p.id === 'custom')
              if (custom) onSelectPreset(custom)
            }}
            disabled={disabled}
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs rounded-lg border border-slate-700 transition-colors cursor-pointer disabled:opacity-50"
          >
            <span>Custom Mission</span>
          </button>
        </div>
      </div>

      {/* Preset Cards Selector */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-[11px] text-slate-400">
          <span className="uppercase tracking-wider font-bold">Select Mission Profile Preset:</span>
          <span className="text-[10px] text-slate-500 italic">
            Loaded from preset — values can still be edited below.
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {MISSION_PRESETS.map((preset) => {
            const isSelected = activePresetId === preset.id
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => onSelectPreset(preset)}
                disabled={disabled}
                className={`text-left p-3.5 rounded-lg border transition-all cursor-pointer flex flex-col justify-between ${
                  isSelected
                    ? 'bg-slate-950 border-cyan-500 ring-1 ring-cyan-500/50 shadow-md'
                    : 'bg-slate-950/60 border-slate-800 hover:border-slate-700 text-slate-400'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className={`text-xs font-bold ${
                        isSelected ? 'text-white' : 'text-slate-300'
                      }`}
                    >
                      {preset.name}
                    </span>
                    <span
                      className={`text-[9px] px-1.5 py-0.5 rounded uppercase font-semibold ${
                        isSelected
                          ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                          : 'bg-slate-900 text-slate-400 border border-slate-800'
                      }`}
                    >
                      {preset.tag}
                    </span>
                  </div>

                  <p className="text-[11px] text-slate-400 font-sans leading-relaxed mb-2">
                    {preset.description}
                  </p>
                </div>

                <div className="pt-2 border-t border-slate-900 text-[10px] space-y-0.5 text-slate-400">
                  <div className="truncate">Alt: <span className="text-slate-200">{preset.altitudeRange}</span></div>
                  <div className="truncate">Inc: <span className="text-slate-200">{preset.inclinationRange}</span></div>
                  <div className="text-[10px] text-cyan-400/90 pt-1 truncate">{preset.purpose}</div>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
