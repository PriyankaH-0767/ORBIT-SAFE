import React, { useState } from 'react'
import type { RunStatusResponse } from '../../types/run'
import type { PlanResponse } from '../../types/plan'
import type { ValidationResponse } from '../../types/validation'

interface MissionBriefingProps {
  run: RunStatusResponse | null
  plan?: PlanResponse | null
  validation?: ValidationResponse | null
}

export const MissionBriefing: React.FC<MissionBriefingProps> = ({
  run,
  plan,
  validation,
}) => {
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false)

  const candidateCount = run?.candidate_count ?? 195
  const rankedCount = run?.ranked_candidate_count ?? candidateCount
  const isCompleted = run?.status === 'completed'
  const hasValidation = validation != null

  // 8 Analysis Pipeline Steps
  const pipelineSteps = [
    {
      num: 1,
      title: 'Mission Defined',
      desc: 'Target deployment window & spacecraft parameters configured',
      status: 'Completed',
    },
    {
      num: 2,
      title: 'Candidate Space Generated',
      desc: `${candidateCount} discrete orbit and delay configurations populated`,
      status: candidateCount > 0 ? 'Completed' : 'Running',
    },
    {
      num: 3,
      title: 'Orbital/Fuel Screening',
      desc: 'Analytic propagation and delta-V budget compliance evaluated',
      status: isCompleted ? 'Completed' : 'Running',
    },
    {
      num: 4,
      title: 'Close-Approach Screening',
      desc: `${run?.conjunction_event_count ?? 0} close-approach encounters identified in threshold`,
      status: isCompleted ? 'Completed' : 'Running',
    },
    {
      num: 5,
      title: 'Risk & Ranking',
      desc: `${rankedCount} candidates sorted via multi-objective Pareto objective`,
      status: isCompleted ? 'Completed' : 'Running',
    },
    {
      num: 6,
      title: 'Visual Analysis',
      desc: 'Interactive 2D risk landscape & 3D pseudofixed globe rendered',
      status: 'Available',
    },
    {
      num: 7,
      title: 'Reference Comparison',
      desc: hasValidation
        ? `Validated against external reference dataset (${validation?.matches.length ?? 0} matches)`
        : 'Empirical cross-reference against external database ready',
      status: hasValidation ? 'Completed' : 'Ready',
    },
    {
      num: 8,
      title: 'Export',
      desc: 'Persisted candidate telemetry and audit logs ready for download',
      status: 'Ready',
    },
  ]

  // Search envelope values (from plan or fallback)
  const altMin = plan?.altitude_min_km ?? 500.0
  const altMax = plan?.altitude_max_km ?? 600.0
  const incMin = plan?.inclination_min_deg ?? 97.0
  const incMax = plan?.inclination_max_deg ?? 98.0
  const delayMin = plan?.delay_min_minutes ?? 0.0
  const delayMax = plan?.delay_max_minutes ?? 720.0
  const screeningDays = plan?.screening_days ?? 3
  const refAlt = plan?.reference_altitude_km ?? 550.0
  const refInc = plan?.reference_inclination_deg ?? 97.5
  const dvBudget = plan?.dv_budget_m_s ?? 100.0
  const scMass = plan?.spacecraft_mass_kg ?? 3.0
  const isp = plan?.isp_seconds ?? 60.0

  return (
    <div
      data-testid="mission-briefing"
      className="p-5 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-xl space-y-6 font-mono text-xs text-slate-300"
    >
      {/* 1. Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="space-y-1">
          <div className="flex items-center space-x-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <h2 className="text-base font-bold text-white tracking-wide uppercase">
              MISSION BRIEFING
            </h2>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase border bg-cyan-950/70 text-cyan-300 border-cyan-800">
              Analysis Workstation
            </span>
          </div>
          <p className="text-xs text-slate-400 font-sans">
            Here is what D-DATO evaluated for this screening run.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsHelpOpen((prev) => !prev)}
          className="self-start sm:self-auto px-3 py-1.5 rounded-lg border border-indigo-500/40 bg-indigo-950/50 hover:bg-indigo-900/60 text-indigo-300 hover:text-white transition-colors flex items-center space-x-2 cursor-pointer"
          aria-expanded={isHelpOpen}
        >
          <span>{isHelpOpen ? '▲ Hide' : '▼ How to Read'}</span>
          <span>D-DATO Results</span>
        </button>
      </div>

      {/* 2. Part 8: "HOW TO READ D-DATO RESULTS" Expandable Panel */}
      {isHelpOpen && (
        <div
          data-testid="how-to-read-panel"
          className="p-4 bg-slate-950/90 border border-indigo-500/40 rounded-xl space-y-3 font-sans"
        >
          <div className="flex items-center space-x-2 font-mono text-xs font-bold text-indigo-300 uppercase tracking-wider">
            <span>ℹ</span>
            <h3>HOW TO READ D-DATO RESULTS</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1">
              <span className="font-mono font-semibold text-white block">1. Candidate</span>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                A specific combination of orbital altitude, inclination, and deployment delay evaluated across the search grid.
              </p>
            </div>

            <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1">
              <span className="font-mono font-semibold text-white block">2. Screening</span>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Early-stage pre-design parametric filtering to identify relative trade-offs before detailed mission architecture.
              </p>
            </div>

            <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1">
              <span className="font-mono font-semibold text-white block">3. Risk score</span>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                The score is a bounded screening heuristic from 0–100. It is not a collision probability.
              </p>
            </div>

            <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1">
              <span className="font-mono font-semibold text-white block">4. Close approach</span>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                An event indicates that propagated trajectories came within the configured screening threshold.
              </p>
            </div>

            <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1">
              <span className="font-mono font-semibold text-white block">5. Miss distance</span>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Reported as the minimum spatial separation identified by the screening process.
              </p>
            </div>

            <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1">
              <span className="font-mono font-semibold text-white block">6. Reference comparison</span>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Shows how D-DATO event findings compare with an external reference dataset under configured matching tolerances.
              </p>
            </div>

            <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1">
              <span className="font-mono font-semibold text-white block">7. Uncertainty</span>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Indicates data/model confidence information available from the screening pipeline.
              </p>
            </div>

            <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1">
              <span className="font-mono font-semibold text-white block">8. Candidate ranking</span>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Orders candidates within the evaluated set using the configured multi-objective heuristic.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3. Part 1: Visual Analysis Timeline */}
      <div className="space-y-2.5">
        <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">
          D-DATO Screening Workflow Timeline:
        </span>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {pipelineSteps.map((step, idx) => (
            <div
              key={step.num}
              className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/90 flex flex-col justify-between space-y-2 relative"
            >
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-900 text-slate-400 border border-slate-800 font-mono">
                    STAGE 0{step.num}
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
                      step.status === 'Completed'
                        ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/80'
                        : step.status === 'Available' || step.status === 'Ready'
                        ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-800/80'
                        : 'bg-amber-950/80 text-amber-300 border border-amber-800/80'
                    }`}
                  >
                    {step.status}
                  </span>
                </div>
                <h4 className="font-bold text-white text-xs font-mono">{step.title}</h4>
                <p className="text-[11px] text-slate-400 font-sans mt-0.5 leading-relaxed">
                  {step.desc}
                </p>
              </div>

              {idx < pipelineSteps.length - 1 && (
                <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-slate-600 text-xs font-mono">
                  →
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 4. Part 2, 3, 6: "YOUR MISSION" SEARCH ENVELOPE CARD */}
      <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800/80 pb-2.5">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-indigo-400" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              YOUR MISSION SEARCH ENVELOPE
            </h3>
          </div>

          <div className="flex items-center space-x-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-950/80 text-indigo-300 border border-indigo-800">
              CANDIDATES EVALUATED: {candidateCount} / 300
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950/80 text-cyan-300 border border-cyan-800">
              SCREENING WINDOW: {screeningDays} DAYS
            </span>
          </div>
        </div>

        <p className="text-xs text-slate-300 font-sans leading-relaxed">
          D-DATO evaluates a bounded set of candidate orbit and deployment configurations for relative screening trade-offs.
        </p>

        {/* Graphical Range Sliders / Bars (Part 6) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
          {/* Altitude Range Visual */}
          <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800/80 space-y-1.5">
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-400 uppercase tracking-wide">Altitude Span</span>
              <strong className="text-cyan-300">{altMin.toFixed(0)} – {altMax.toFixed(0)} km</strong>
            </div>
            <div className="flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
              <span>{altMin.toFixed(0)}</span>
              <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden flex items-center">
                <div className="w-full h-full bg-cyan-500/70 rounded-full" />
              </div>
              <span>{altMax.toFixed(0)} km</span>
            </div>
            <p className="text-[10px] text-slate-400 font-sans">
              Changes the orbital altitude being screened.
            </p>
          </div>

          {/* Inclination Range Visual */}
          <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800/80 space-y-1.5">
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-400 uppercase tracking-wide">Inclination Span</span>
              <strong className="text-cyan-300">{incMin.toFixed(1)}° – {incMax.toFixed(1)}°</strong>
            </div>
            <div className="flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
              <span>{incMin.toFixed(1)}°</span>
              <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden flex items-center">
                <div className="w-full h-full bg-indigo-500/70 rounded-full" />
              </div>
              <span>{incMax.toFixed(1)}°</span>
            </div>
            <p className="text-[10px] text-slate-400 font-sans">
              Changes the orbital-plane orientation.
            </p>
          </div>

          {/* Deployment Delay Visual */}
          <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800/80 space-y-1.5">
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-400 uppercase tracking-wide">Deployment Delay</span>
              <strong className="text-cyan-300">{delayMin.toFixed(0)} – {delayMax.toFixed(0)} min</strong>
            </div>
            <div className="flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
              <span>{delayMin.toFixed(0)}</span>
              <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden flex items-center">
                <div className="w-full h-full bg-emerald-500/70 rounded-full" />
              </div>
              <span>{delayMax.toFixed(0)} min</span>
            </div>
            <p className="text-[10px] text-slate-400 font-sans">
              Explores different deployment timing windows.
            </p>
          </div>
        </div>

        {/* Mission Intent Explanations (Part 3) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-2.5 bg-slate-950/60 rounded-lg border border-slate-800 text-[11px] text-slate-300">
          <div>
            <strong className="text-white block font-mono text-[10px] uppercase">Fuel Budget:</strong>
            <span className="text-slate-400">Provides the propulsion budget used for candidate budget checks.</span>
          </div>
          <div>
            <strong className="text-white block font-mono text-[10px] uppercase">Screening Duration:</strong>
            <span className="text-slate-400">Defines how long the candidate/debris geometry is evaluated.</span>
          </div>
        </div>

        {/* Spacecraft & Propulsion Specs (Part 2 & 3) */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 text-[11px]">
          <div className="p-2.5 bg-slate-900/50 rounded border border-slate-800/70">
            <span className="text-slate-400 block text-[10px] uppercase">Delta-V Budget</span>
            <span className="text-white font-bold">{dvBudget.toFixed(1)} m/s</span>
            <span className="text-[10px] text-slate-500 block">Candidate budget check</span>
          </div>

          <div className="p-2.5 bg-slate-900/50 rounded border border-slate-800/70">
            <span className="text-slate-400 block text-[10px] uppercase">Spacecraft Mass</span>
            <span className="text-white font-bold">{scMass.toFixed(1)} kg</span>
            <span className="text-[10px] text-slate-500 block">Wet mass benchmark</span>
          </div>

          <div className="p-2.5 bg-slate-900/50 rounded border border-slate-800/70">
            <span className="text-slate-400 block text-[10px] uppercase">Specific Impulse</span>
            <span className="text-white font-bold">{isp.toFixed(1)} s</span>
            <span className="text-[10px] text-slate-500 block">Tsiolkovsky baseline</span>
          </div>

          <div className="p-2.5 bg-slate-900/50 rounded border border-slate-800/70">
            <span className="text-slate-400 block text-[10px] uppercase">Reference Orbit</span>
            <span className="text-white font-bold">{refAlt.toFixed(0)} km • {refInc.toFixed(1)}°</span>
            <span className="text-[10px] text-slate-500 block">Injection midpoint</span>
          </div>
        </div>
      </div>
    </div>
  )
}
