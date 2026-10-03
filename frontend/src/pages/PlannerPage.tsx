import React, { useState } from 'react'
import { PlannerHero } from '../components/planner/PlannerHero'
import { PlannerForm } from '../components/planner/PlannerForm'
import { RunProgressPanel } from '../components/run/RunProgressPanel'
import { useRunPolling } from '../hooks/useRunPolling'
import { createPlan } from '../api/plans'
import { getDemoRun } from '../api/demo'
import { navigateTo } from '../utils/router'
import { DEFAULT_PLAN_FORM, type PlanCreateRequest } from '../types/plan'

export const PlannerPage: React.FC = () => {
  const [activePlanId, setActivePlanId] = useState<string | null>(null)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [lastSubmittedValues, setLastSubmittedValues] = useState<PlanCreateRequest>(DEFAULT_PLAN_FORM)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Phase P28: Instant demo state
  const [isDemoLoading, setIsDemoLoading] = useState<boolean>(false)
  const [demoError, setDemoError] = useState<string | null>(null)

  // Polling hook for active run (used for non-demo 90s runs)
  const {
    run,
    isLoading: isPollingLoading,
    networkError,
  } = useRunPolling(activeRunId)

  const handleFormSubmit = async (values: PlanCreateRequest) => {
    setIsSubmitting(true)
    setSubmitError(null)
    setLastSubmittedValues(values)

    try {
      const response = await createPlan(values)
      setActivePlanId(response.plan_id)
      setActiveRunId(response.run_id)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to submit mission plan'
      setSubmitError(msg)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Phase P28: Instant demo — call /api/v1/demo/run and navigate directly to results
  const handleOpenDemo = async () => {
    setIsDemoLoading(true)
    setDemoError(null)
    try {
      const demoResp = await getDemoRun()
      // Navigate directly to the completed demo run results page
      navigateTo(`/results/${demoResp.run_id}`)
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Failed to load demo. Please ensure the backend is running.'
      setDemoError(msg)
    } finally {
      setIsDemoLoading(false)
    }
  }

  const handleBackToPlanner = () => {
    setActiveRunId(null)
    setSubmitError(null)
  }

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {activeRunId ? (
        <RunProgressPanel
          run={run}
          runId={activeRunId}
          planId={activePlanId}
          isLoading={isPollingLoading}
          networkError={networkError}
          onReset={handleBackToPlanner}
        />
      ) : (
        <div className="space-y-6">
          <PlannerHero
            onStartDemo={handleOpenDemo}
            isDemoLoading={isDemoLoading}
            isDemoReady={true}
          />

          {/* Phase P28: Demo error display */}
          {demoError && (
            <div
              role="alert"
              className="max-w-5xl mx-auto px-4 py-3 rounded-lg bg-red-950/60 border border-red-800 text-red-300 text-sm font-mono"
            >
              <span className="font-bold">DEMO ERROR: </span>
              {demoError}
            </div>
          )}

          <div className="max-w-5xl mx-auto border-b border-slate-800 pb-4">
            <h2 className="text-xl font-bold tracking-tight text-white font-mono">
              Mission Planning &amp; Screening Envelope
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Configure orbital parameters and deployment window search constraints to screen against cataloged orbital debris.
            </p>
          </div>

          <PlannerForm
            initialValues={lastSubmittedValues}
            onSubmit={handleFormSubmit}
            isSubmitting={isSubmitting}
            apiError={submitError}
            onOpenDemo={handleOpenDemo}
            isDemoLoading={isDemoLoading}
          />
        </div>
      )}
    </main>
  )
}
