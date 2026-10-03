import React from 'react'

interface PlannerHeroProps {
  onStartDemo?: () => void
  isDemoLoading?: boolean
  isDemoReady?: boolean
}

export const PlannerHero: React.FC<PlannerHeroProps> = ({
  onStartDemo,
  isDemoLoading = false,
  isDemoReady = true,
}) => {
  const capabilities = [
    'Generate candidate orbit/deployment combinations',
    'Estimate propulsion demand',
    'Screen close approaches',
    'Calculate bounded screening risk',
    'Visualize candidate trade-offs',
    'Validate against reference data',
    'Export analysis',
  ]

  const missionFlowSteps = [
    { num: '01', title: 'DEFINE MISSION', desc: 'Specify bounded altitude, inclination & delay grid' },
    { num: '02', title: 'SCREEN CANDIDATES', desc: 'Run SGP4 propagation & close-approach screening' },
    { num: '03', title: 'COMPARE RESULTS', desc: 'Inspect propulsion demand & candidate trade-off ranking' },
    { num: '04', title: 'VISUALIZE', desc: 'Explore 3D orbit geometry & interactive risk landscape' },
    { num: '05', title: 'VALIDATE', desc: 'Benchmark against external reference catalog' },
    { num: '06', title: 'EXPORT', desc: 'Download reproducible CSV package & PDF report' },
  ]

  const screenedAspects = [
    { title: 'Candidate Orbit Configurations', desc: 'Bounded altitude & inclination parametric search' },
    { title: 'Deployment Windows', desc: 'Timing delays across orbital dispersion corridor' },
    { title: 'Propulsion Demand', desc: 'J2-assisted delta-V & propellant mass estimation' },
    { title: 'Debris Close Approaches', desc: 'SGP4 temporal conjunction detection against catalog' },
    { title: 'Bounded Screening Risk', desc: 'Multi-attribute 0–100 heuristic screening indicator' },
    { title: 'Candidate Trade-Offs', desc: 'Relative trade-offs across evaluated search envelope' },
  ]

  return (
    <div
      data-testid="planner-hero"
      className="p-6 sm:p-8 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-xl space-y-6 font-mono"
    >
      {/* Primary Brand & Purpose */}
      <div className="space-y-3 border-b border-slate-800/80 pb-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center space-x-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-xs uppercase tracking-widest text-cyan-400 font-bold">
              EARLY-STAGE PRE-DESIGN SCREENING
            </span>
            <span className="px-2 py-0.5 text-[10px] rounded bg-slate-800 text-slate-300 border border-slate-700">
              Smart India Hackathon 2026 • Problem Statement 26209
            </span>
          </div>

          {/* Part 11: Screening Mode Indicator */}
          <div
            data-testid="screening-mode-indicator"
            className="flex items-center space-x-2 px-2.5 py-1 rounded bg-slate-950 border border-cyan-800/60 text-[11px]"
          >
            <span className="text-slate-400 font-semibold uppercase text-[10px]">Screening Mode:</span>
            <span className="font-bold text-cyan-300 uppercase">Offline Demo</span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-400 text-[10px]">Source: CelesTrak (Public LEO)</span>
            <span className="text-slate-600 hidden sm:inline">|</span>
            <span className="text-slate-400 text-[10px] hidden sm:inline">Frame: TEME • UTC</span>
          </div>
        </div>

        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight font-sans">
              D-DATO
            </h1>
            <p className="text-sm sm:text-base font-semibold text-cyan-300 font-sans mt-0.5">
              Debris-Aware Orbit & Deployment-Window Planner
            </p>
            <p className="text-xs sm:text-sm text-slate-300 font-sans leading-relaxed pt-1">
              Screen candidate CubeSat deployment windows before detailed mission design.
            </p>
          </div>

          {/* Part 15 & 16: Immediate Landing Viewport Demo CTA */}
          {onStartDemo && (
            <div className="self-start md:self-auto flex flex-col items-end gap-1">
              <button
                type="button"
                data-testid="hero-guided-demo-btn"
                onClick={onStartDemo}
                disabled={isDemoLoading}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-slate-950 font-bold font-mono text-xs uppercase tracking-wider shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/30 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-60"
              >
                <span>⚡</span>
                <span>{isDemoLoading ? 'LOADING DEMO…' : 'START GUIDED DEMO'}</span>
                {isDemoReady && !isDemoLoading && (
                  <span className="px-1.5 py-0.5 rounded bg-slate-950/80 text-cyan-300 text-[10px] border border-cyan-800">
                    DEMO READY
                  </span>
                )}
              </button>
              <span className="text-[10px] text-slate-400 font-mono">
                Deterministic evaluation • 195 candidates
              </span>
            </div>
          )}
        </div>

        {/* Part 9: Problem / Solution Intro */}
        <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2 font-sans">
          <div className="flex items-center space-x-2 text-amber-300 font-mono text-xs font-bold uppercase tracking-wider">
            <span>⚠️</span>
            <span>THE EARLY-STAGE CHALLENGE</span>
          </div>
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
            CubeSat teams may need to compare multiple orbit and deployment configurations before detailed mission design.
          </p>
          <div className="text-xs text-slate-400 pt-1 font-mono">
            <span className="text-slate-300 font-bold uppercase text-[11px] block mb-1.5">
              D-DATO helps screen:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {screenedAspects.map((item, idx) => (
                <div
                  key={idx}
                  className="bg-slate-900/80 border border-slate-800/80 rounded-lg p-2 flex items-start space-x-2"
                >
                  <span className="text-cyan-400 font-bold text-sm leading-none mt-0.5">›</span>
                  <div>
                    <span className="text-white text-xs font-semibold block">{item.title}</span>
                    <span className="text-[10px] text-slate-400 block font-sans">{item.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Capabilities Summary Grid */}
        <div className="space-y-2 pt-2">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
            Core Screening Capabilities
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs text-slate-300">
            {capabilities.map((cap, idx) => (
              <div
                key={idx}
                className="flex items-center space-x-2 bg-slate-950/60 border border-slate-800/80 rounded-lg px-3 py-1.5"
              >
                <span className="text-cyan-400 font-bold text-sm">›</span>
                <span className="text-[11px] text-slate-200">{cap}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Part 10: Mission Flow Strip */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider font-bold">
          <span>Mission Screening Lifecycle Flow</span>
          <span className="text-[10px] text-slate-500 font-normal">Define → Screen → Compare → Visualize → Validate → Export</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {missionFlowSteps.map((step, idx) => (
            <div
              key={step.num}
              className="flex flex-col justify-between bg-slate-950 border border-slate-800/90 rounded-xl p-3 space-y-1 hover:border-cyan-800/60 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="w-5 h-5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 text-[10px] font-bold flex items-center justify-center shrink-0">
                  {step.num}
                </span>
                {idx < missionFlowSteps.length - 1 && (
                  <span className="text-slate-600 text-xs hidden lg:inline font-bold">
                    →
                  </span>
                )}
              </div>
              <div>
                <span className="text-xs font-bold text-white tracking-wider block">
                  {step.title}
                </span>
                <span className="text-[10px] text-slate-400 font-sans leading-tight block mt-0.5">
                  {step.desc}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Non-Operational Positioning Notice */}
      <div className="p-3 bg-slate-950/80 border border-cyan-950/60 rounded-lg text-[11px] text-slate-400 flex items-start space-x-2">
        <span className="text-cyan-400 text-sm leading-none shrink-0 mt-0.5">ℹ</span>
        <span>
          <strong className="text-slate-200">Non-Operational Planning Scope:</strong> D-DATO provides early-stage trajectory screening evidence to evaluate relative trade-offs between propulsion expenditure and close-approach debris encounters. It is not an operational collision avoidance or flight maneuver clearance tool.
        </span>
      </div>
    </div>
  )
}
