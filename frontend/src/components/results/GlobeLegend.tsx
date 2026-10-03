import React from 'react'

export const GlobeLegend: React.FC = () => {
  return (
    <div className="bg-slate-900/90 backdrop-blur border border-slate-800 rounded-lg p-3 text-xs font-mono space-y-2.5">
      <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
        Trajectory & Marker Classification
      </div>

      <div className="flex flex-wrap items-center gap-4 text-slate-300">
        <div className="flex items-center space-x-2">
          <span className="inline-block w-4 h-0.5 bg-cyan-400 shadow-sm shadow-cyan-500/50"></span>
          <span>Candidate orbit</span>
        </div>

        <div className="flex items-center space-x-2">
          <span className="inline-block w-4 h-0.5 bg-amber-400 shadow-sm shadow-amber-500/50"></span>
          <span>Debris trajectory</span>
        </div>

        <div className="flex items-center space-x-2">
          <span className="inline-block w-2.5 h-2.5 bg-rose-400 rotate-45 border border-rose-200"></span>
          <span>Conjunction event</span>
        </div>

        <div className="flex items-center space-x-2">
          <span className="inline-block w-4 h-0.5 bg-white border-b-2 border-dotted border-cyan-300"></span>
          <span className="text-slate-400">Selected candidate highlight</span>
        </div>

        <div className="flex items-center space-x-2">
          <div className="flex -space-x-1">
            <span className="inline-block w-2.5 h-1.5 rounded-sm bg-cyan-400"></span>
            <span className="inline-block w-2.5 h-1.5 rounded-sm bg-emerald-400"></span>
            <span className="inline-block w-2.5 h-1.5 rounded-sm bg-amber-400"></span>
            <span className="inline-block w-2.5 h-1.5 rounded-sm bg-purple-400"></span>
          </div>
          <span className="text-indigo-300">Multi-candidate comparison palette</span>
        </div>
      </div>

      <div className="border-t border-slate-800/80 pt-2 space-y-1 text-[11px] text-slate-400">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
          <div>
            <span className="text-slate-300 font-medium">Coordinate data:</span> TEME (True Equator Mean Equinox)
          </div>
          <div>
            <span className="text-slate-300 font-medium">Display transform:</span> TEME → Cesium pseudo-fixed frame
          </div>
          <div>
            <span className="text-slate-300 font-medium">Time scale:</span> UTC (Cesium UT1≈UTC assumption)
          </div>
          <div>
            <span className="text-slate-300 font-medium">Position units:</span> km (converted to meters for Cesium rendering)
          </div>
        </div>
        <div className="text-[10px] text-slate-400 italic pt-1 border-t border-slate-800/40">
          Visualization only — D-DATO is not an operational conjunction assessment or maneuver-planning system.
        </div>
      </div>
    </div>
  )
}
