import React, { useState } from 'react'
import type {
  ValidationResponse,
  ValidationExecutionRequest,
} from '../../types/validation'
import { ValidationControls } from './ValidationControls'
import { ValidationProvenance } from './ValidationProvenance'
import { ValidationSummaryPanel } from './ValidationSummaryPanel'
import { ValidationMatchesTable } from './ValidationMatchesTable'
import { ValidationDdatoOnlyTable } from './ValidationDdatoOnlyTable'
import { ValidationExternalOnlyTable } from './ValidationExternalOnlyTable'

export interface ValidationSectionProps {
  validation: ValidationResponse | null
  isLoading: boolean
  isRunning: boolean
  error: string | null
  onRunValidation: (request: ValidationExecutionRequest) => void
  onRetry: () => void
  onSelectCandidateId?: (candidateId: string) => void
}

type ComparisonTab = 'matches' | 'ddato_only' | 'external_only'

export const ValidationSection: React.FC<ValidationSectionProps> = ({
  validation,
  isLoading,
  isRunning,
  error,
  onRunValidation,
  onRetry,
  onSelectCandidateId,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(true)
  const [activeTab, setActiveTab] = useState<ComparisonTab>('matches')

  return (
    <section className="space-y-4" aria-labelledby="validation-heading">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-3">
        <div>
          <h3
            id="validation-heading"
            className="text-base font-bold text-white font-mono flex flex-wrap items-center gap-2"
          >
            <span className="text-cyan-400">REFERENCE COMPARISON</span>
            <span className="text-slate-500 hidden sm:inline">•</span>
            <span>External Reference Validation</span>
            {validation && (
              <span className="text-xs px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800/80 font-normal">
                {validation.matches.length} matched
              </span>
            )}
          </h3>
          <p className="text-xs text-cyan-300/90 font-mono mt-0.5">
            Compare D-DATO event findings with the selected external reference dataset.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className="self-start sm:self-auto px-3 py-1 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded border border-slate-700 text-xs font-mono transition-colors cursor-pointer"
        >
          {isOpen ? 'Collapse Section' : 'Expand Section'}
        </button>
      </div>

      {isOpen && (
        <div className="space-y-6">
          {/* Part 12: 3-Step Validation Story Explanation */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 font-mono">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-center text-center">
              <div className="p-3 bg-slate-950/70 border border-cyan-900/40 rounded-lg">
                <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">Step 1</div>
                <div className="text-xs font-bold text-cyan-300">D-DATO EVENTS</div>
                <p className="text-[11px] text-slate-400 mt-1 font-sans">Screened close-approach candidates</p>
              </div>
              <div className="p-3 bg-slate-950/70 border border-indigo-900/40 rounded-lg relative">
                <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">Step 2</div>
                <div className="text-xs font-bold text-indigo-300">MATCHING CRITERIA</div>
                <p className="text-[11px] text-slate-400 mt-1 font-sans">Configured time (Δt) & miss distance (Δd) tolerances</p>
              </div>
              <div className="p-3 bg-slate-950/70 border border-emerald-900/40 rounded-lg">
                <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">Step 3</div>
                <div className="text-xs font-bold text-emerald-300">REFERENCE COMPARISON</div>
                <p className="text-[11px] text-slate-400 mt-1 font-sans">Benchmark pairing against external catalog events</p>
              </div>
            </div>
            <p className="text-xs text-slate-300 mt-3 pt-3 border-t border-slate-800/80 font-sans leading-relaxed">
              The comparison checks whether D-DATO events can be paired with external reference events within configured temporal and spatial tolerances.
            </p>
          </div>
          {/* Loading Initial State */}
          {isLoading ? (
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-8 text-center space-y-3 font-mono">
              <div className="w-7 h-7 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <p className="text-xs text-slate-400">Loading validation results…</p>
            </div>
          ) : error ? (
            /* Error State */
            <div className="p-5 bg-rose-950/30 border border-rose-800/80 rounded-xl text-xs font-mono text-rose-300 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-rose-200">
                  {error}
                </span>
                <button
                  type="button"
                  onClick={onRetry}
                  className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded border border-slate-700 cursor-pointer"
                >
                  Retry
                </button>
              </div>
              <p className="text-[11px] text-slate-400">
                You may reconfigure tolerance parameters below and attempt external validation again.
              </p>
              <ValidationControls
                onRunValidation={onRunValidation}
                isRunning={isRunning}
              />
            </div>
          ) : !validation ? (
            /* Empty State: Not yet validated */
            <div className="space-y-4">
              <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6 text-center space-y-2">
                <div className="w-10 h-10 mx-auto rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 font-mono text-sm">
                  VS
                </div>
                <h4 className="text-sm font-semibold text-slate-200 font-mono">
                  No External Validation Executed Yet
                </h4>
                <p className="text-xs font-mono text-slate-400 max-w-xl mx-auto">
                  No external reference validation has been run for this screening run. Configure comparison tolerances below to benchmark screening output against SOCRATES.
                </p>
              </div>

              <ValidationControls
                onRunValidation={onRunValidation}
                isRunning={isRunning}
              />
            </div>
          ) : (
            /* Populated Validation Results */
            <div className="space-y-6">
              {/* Provenance Panel */}
              <ValidationProvenance
                source={validation.source}
                status={validation.status}
                sourceFetchedAt={validation.source_fetched_at}
                validationCreatedAt={validation.validation_created_at}
                validationId={validation.validation_id}
              />

              {/* Summary Metrics */}
              <ValidationSummaryPanel summary={validation.summary} />

              {/* Comparison Tables Tab Bar */}
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 pb-2">
                  <button
                    type="button"
                    onClick={() => setActiveTab('matches')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors cursor-pointer ${
                      activeTab === 'matches'
                        ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-800'
                        : 'bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-800'
                    }`}
                  >
                    Matched Events ({validation.matches.length})
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('ddato_only')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors cursor-pointer ${
                      activeTab === 'ddato_only'
                        ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-800'
                        : 'bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-800'
                    }`}
                  >
                    D-DATO-only ({validation.d_dato_only.length})
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('external_only')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors cursor-pointer ${
                      activeTab === 'external_only'
                        ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-800'
                        : 'bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-800'
                    }`}
                  >
                    External-only ({validation.external_only.length})
                  </button>
                </div>

                {/* Tab Content */}
                {activeTab === 'matches' && (
                  <ValidationMatchesTable
                    matches={validation.matches}
                    onSelectCandidateId={onSelectCandidateId}
                  />
                )}

                {activeTab === 'ddato_only' && (
                  <ValidationDdatoOnlyTable
                    events={validation.d_dato_only}
                    onSelectCandidateId={onSelectCandidateId}
                  />
                )}

                {activeTab === 'external_only' && (
                  <ValidationExternalOnlyTable events={validation.external_only} />
                )}
              </div>

              {/* Re-run / Reconfigure Controls */}
              <div className="pt-2">
                <ValidationControls
                  onRunValidation={onRunValidation}
                  isRunning={isRunning}
                />
              </div>

              {/* Validation Notes & Non-Operational Disclaimers */}
              {validation.notes && validation.notes.length > 0 && (
                <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-4 space-y-2">
                  <h5 className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
                    Validation Notes & Disclaimers:
                  </h5>
                  <ul className="space-y-1 text-xs font-mono text-slate-300 list-disc list-inside">
                    {validation.notes.map((note, index) => (
                      <li key={index} className="leading-relaxed">
                        {note}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
