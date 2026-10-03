import React, { useState, useMemo } from 'react'
import { FormField } from './FormField'
import { CandidatePreview } from './CandidatePreview'
import { calculateCandidateCount, MAX_CANDIDATES } from '../../utils/grid'
import { DEFAULT_PLAN_FORM, type PlanCreateRequest } from '../../types/plan'

interface PlannerFormProps {
  initialValues?: PlanCreateRequest
  onSubmit: (values: PlanCreateRequest) => Promise<void>
  isSubmitting?: boolean
  apiError?: string | null
}

export const PlannerForm: React.FC<PlannerFormProps> = ({
  initialValues,
  onSubmit,
  isSubmitting = false,
  apiError = null,
}) => {
  const [form, setForm] = useState<PlanCreateRequest>(initialValues || DEFAULT_PLAN_FORM)

  const updateField = <K extends keyof PlanCreateRequest>(key: K, value: PlanCreateRequest[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  // Client-side validations
  const errors = useMemo(() => {
    const errs: Record<string, string> = {}

    // Section A
    if (form.altitude_min_km <= 0) errs.altitude_min_km = 'Min altitude must be > 0'
    if (form.altitude_max_km <= 0) errs.altitude_max_km = 'Max altitude must be > 0'
    if (form.altitude_min_km > form.altitude_max_km) {
      errs.altitude_min_km = 'Min altitude cannot exceed max altitude'
    }
    if (form.altitude_step_km <= 0) errs.altitude_step_km = 'Step size must be > 0'

    if (form.inclination_min_deg < 0 || form.inclination_min_deg > 180) {
      errs.inclination_min_deg = 'Inclination must be between 0° and 180°'
    }
    if (form.inclination_max_deg < 0 || form.inclination_max_deg > 180) {
      errs.inclination_max_deg = 'Inclination must be between 0° and 180°'
    }
    if (form.inclination_min_deg > form.inclination_max_deg) {
      errs.inclination_min_deg = 'Min inclination cannot exceed max inclination'
    }
    if (form.inclination_step_deg <= 0) errs.inclination_step_deg = 'Step size must be > 0'

    if (form.delay_min_minutes < 0) errs.delay_min_minutes = 'Delay cannot be negative'
    if (form.delay_min_minutes > form.delay_max_minutes) {
      errs.delay_min_minutes = 'Min delay cannot exceed max delay'
    }
    if (form.delay_step_minutes <= 0) errs.delay_step_minutes = 'Step size must be > 0'

    // Section C
    if (form.screening_days < 1 || form.screening_days > 7) {
      errs.screening_days = 'Screening duration must be between 1 and 7 days'
    }

    // Section D
    if (form.reference_altitude_km <= 0) errs.reference_altitude_km = 'Altitude must be > 0'
    if (form.reference_inclination_deg < 0 || form.reference_inclination_deg > 180) {
      errs.reference_inclination_deg = 'Inclination must be between 0° and 180°'
    }
    if (form.dv_budget_m_s < 0) errs.dv_budget_m_s = 'Delta-V cannot be negative'
    if (form.spacecraft_mass_kg <= 0) errs.spacecraft_mass_kg = 'Mass must be > 0'
    if (form.isp_seconds <= 0) errs.isp_seconds = 'Specific impulse must be > 0'

    // Section E
    if (form.fuel_weight < 0 || form.fuel_weight > 1) {
      errs.fuel_weight = 'Fuel weight must be between 0.0 and 1.0'
    }
    if (form.risk_weight < 0 || form.risk_weight > 1) {
      errs.risk_weight = 'Risk weight must be between 0.0 and 1.0'
    }
    const weightSum = form.fuel_weight + form.risk_weight
    if (Math.abs(weightSum - 1.0) > 1e-4) {
      errs.weights = `Fuel (${form.fuel_weight.toFixed(2)}) and Risk (${form.risk_weight.toFixed(2)}) weights must sum to 1.0 (currently ${weightSum.toFixed(2)})`
    }

    return errs
  }, [form])

  const { count: candidateCount, isValid: gridValid } = useMemo(() => {
    return calculateCandidateCount(form)
  }, [form])

  const isGridOverLimit = candidateCount > MAX_CANDIDATES
  const hasValidationErrors = Object.keys(errors).length > 0
  const canSubmit = !hasValidationErrors && gridValid && !isGridOverLimit && !isSubmitting

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return

    // Clean up empty epoch string if user omitted it so backend defaults to now_utc
    const payload: PlanCreateRequest = {
      ...form,
      epoch_start: form.epoch_start && form.epoch_start.trim().length > 0 ? form.epoch_start : undefined,
    }
    onSubmit(payload)
  }

  const handleReset = () => {
    setForm(DEFAULT_PLAN_FORM)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-5xl mx-auto pb-12">
      {apiError && (
        <div className="p-4 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-300 text-sm flex items-start space-x-2">
          <span className="font-bold text-rose-400">Error:</span>
          <span>{apiError}</span>
        </div>
      )}

      {/* Candidate Count Preview Sticky Banner */}
      <div className="sticky top-16 z-10 shadow-lg">
        <CandidatePreview params={form} />
      </div>

      {/* SECTION A — Search Space */}
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow-sm space-y-4">
        <div className="border-b border-slate-800/80 pb-2 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white tracking-wide uppercase font-mono">
              Section A: Candidate Search Space
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Defines the altitude, inclination, and deployment delay evaluation grid.
            </p>
          </div>
          <span className="text-[11px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
            Grid Space
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <FormField
            id="altitude_min_km"
            label="Min Altitude"
            unit="km"
            value={form.altitude_min_km}
            onChange={(v) => updateField('altitude_min_km', Number(v))}
            error={errors.altitude_min_km}
          />
          <FormField
            id="altitude_max_km"
            label="Max Altitude"
            unit="km"
            value={form.altitude_max_km}
            onChange={(v) => updateField('altitude_max_km', Number(v))}
            error={errors.altitude_max_km}
          />
          <FormField
            id="altitude_step_km"
            label="Altitude Step"
            unit="km"
            value={form.altitude_step_km}
            onChange={(v) => updateField('altitude_step_km', Number(v))}
            error={errors.altitude_step_km}
          />

          <FormField
            id="inclination_min_deg"
            label="Min Inclination"
            unit="°"
            value={form.inclination_min_deg}
            onChange={(v) => updateField('inclination_min_deg', Number(v))}
            error={errors.inclination_min_deg}
          />
          <FormField
            id="inclination_max_deg"
            label="Max Inclination"
            unit="°"
            value={form.inclination_max_deg}
            onChange={(v) => updateField('inclination_max_deg', Number(v))}
            error={errors.inclination_max_deg}
          />
          <FormField
            id="inclination_step_deg"
            label="Inclination Step"
            unit="°"
            value={form.inclination_step_deg}
            onChange={(v) => updateField('inclination_step_deg', Number(v))}
            error={errors.inclination_step_deg}
          />

          <FormField
            id="delay_min_minutes"
            label="Min Delay"
            unit="min"
            value={form.delay_min_minutes}
            onChange={(v) => updateField('delay_min_minutes', Number(v))}
            error={errors.delay_min_minutes}
          />
          <FormField
            id="delay_max_minutes"
            label="Max Delay"
            unit="min"
            value={form.delay_max_minutes}
            onChange={(v) => updateField('delay_max_minutes', Number(v))}
            error={errors.delay_max_minutes}
          />
          <FormField
            id="delay_step_minutes"
            label="Delay Step"
            unit="min"
            value={form.delay_step_minutes}
            onChange={(v) => updateField('delay_step_minutes', Number(v))}
            error={errors.delay_step_minutes}
          />
        </div>
      </div>

      {/* SECTION B — Orbit Setup */}
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow-sm space-y-4">
        <div className="border-b border-slate-800/80 pb-2">
          <h2 className="text-sm font-semibold text-white tracking-wide uppercase font-mono">
            Section B: Orbit Setup & Perturbations
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Initial orbital parameters and Earth nodal precession coupling.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <FormField
            id="raan_deg"
            label="Base RAAN (Ω₀)"
            unit="°"
            value={form.raan_deg}
            onChange={(v) => updateField('raan_deg', Number(v))}
            helpText="Right Ascension of Ascending Node at epoch"
          />
          <FormField
            id="u0_deg"
            label="Initial Arg of Lat (u₀)"
            unit="°"
            value={form.u0_deg}
            onChange={(v) => updateField('u0_deg', Number(v))}
            helpText="Argument of latitude at deployment epoch"
          />
          <FormField
            id="raan_delay_coupling_deg_per_min"
            label="RAAN-Delay Coupling"
            unit="°/min"
            value={form.raan_delay_coupling_deg_per_min}
            onChange={(v) => updateField('raan_delay_coupling_deg_per_min', Number(v))}
            helpText="Standard Earth nodal drift coupling constant"
          />
        </div>
      </div>

      {/* SECTION C — Screening Duration */}
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow-sm space-y-4">
        <div className="border-b border-slate-800/80 pb-2">
          <h2 className="text-sm font-semibold text-white tracking-wide uppercase font-mono">
            Section C: Screening Time Horizon
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Deployment epoch and close-approach propagation window.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            id="epoch_start"
            label="Planning Epoch Start (UTC)"
            type="text"
            value={form.epoch_start || ''}
            onChange={(v) => updateField('epoch_start', String(v))}
            helpText="Leave blank for immediate deployment (now_utc), or specify ISO-8601 string"
          />
          <FormField
            id="screening_days"
            label="Screening Duration"
            unit="days"
            value={form.screening_days}
            min={1}
            max={7}
            step={1}
            onChange={(v) => updateField('screening_days', Math.round(Number(v)))}
            helpText="Duration for SGP4 debris propagation (1 to 7 days)"
            error={errors.screening_days}
          />
        </div>
      </div>

      {/* SECTION D — Reference / Propulsion */}
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow-sm space-y-4">
        <div className="border-b border-slate-800/80 pb-2">
          <h2 className="text-sm font-semibold text-white tracking-wide uppercase font-mono">
            Section D: Reference Orbit & Propulsion Budget
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Baseline injection orbit and spacecraft maneuver capabilities.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          <FormField
            id="reference_altitude_km"
            label="Reference Altitude"
            unit="km"
            value={form.reference_altitude_km}
            onChange={(v) => updateField('reference_altitude_km', Number(v))}
            error={errors.reference_altitude_km}
          />
          <FormField
            id="reference_inclination_deg"
            label="Reference Inclination"
            unit="°"
            value={form.reference_inclination_deg}
            onChange={(v) => updateField('reference_inclination_deg', Number(v))}
            error={errors.reference_inclination_deg}
          />
          <FormField
            id="dv_budget_m_s"
            label="Delta-V Budget"
            unit="m/s"
            value={form.dv_budget_m_s}
            onChange={(v) => updateField('dv_budget_m_s', Number(v))}
            error={errors.dv_budget_m_s}
          />
          <FormField
            id="spacecraft_mass_kg"
            label="Spacecraft Mass"
            unit="kg"
            value={form.spacecraft_mass_kg}
            onChange={(v) => updateField('spacecraft_mass_kg', Number(v))}
            error={errors.spacecraft_mass_kg}
          />
          <FormField
            id="isp_seconds"
            label="Specific Impulse (Isp)"
            unit="s"
            value={form.isp_seconds}
            onChange={(v) => updateField('isp_seconds', Number(v))}
            error={errors.isp_seconds}
          />
        </div>
      </div>

      {/* SECTION E — Objective Weights */}
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow-sm space-y-4">
        <div className="border-b border-slate-800/80 pb-2">
          <h2 className="text-sm font-semibold text-white tracking-wide uppercase font-mono">
            Section E: Multi-Objective Ranking Weights
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Weights balancing fuel expenditure vs. close-approach debris risk (must sum to 1.0).
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField
            id="fuel_weight"
            label="Fuel Consumption Weight"
            step="0.05"
            min="0"
            max="1"
            value={form.fuel_weight}
            onChange={(v) => {
              const val = Number(v)
              updateField('fuel_weight', val)
            }}
            error={errors.fuel_weight}
          />
          <FormField
            id="risk_weight"
            label="Debris Screening Risk Weight"
            step="0.05"
            min="0"
            max="1"
            value={form.risk_weight}
            onChange={(v) => {
              const val = Number(v)
              updateField('risk_weight', val)
            }}
            error={errors.risk_weight}
          />
        </div>
        {errors.weights && (
          <p className="text-xs text-rose-400 font-medium" role="alert">
            {errors.weights}
          </p>
        )}
      </div>

      {/* SECTION F — Data Source & Mode */}
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow-sm space-y-4">
        <div className="border-b border-slate-800/80 pb-2">
          <h2 className="text-sm font-semibold text-white tracking-wide uppercase font-mono">
            Section F: Catalog Data Source & Execution Mode
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Ingestion source and offline demonstration environment options.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
          <div>
            <label htmlFor="data_source" className="text-xs font-medium text-slate-300 block mb-1">
              Catalog Data Source
            </label>
            <select
              id="data_source"
              name="data_source"
              value={form.data_source}
              onChange={(e) => updateField('data_source', e.target.value as 'celestrak' | 'spacetrack')}
              className="w-full px-2.5 py-1.5 text-sm bg-slate-900 border border-slate-700 rounded-md font-mono text-slate-100 focus:outline-none focus:border-indigo-500"
            >
              <option value="celestrak">CelesTrak (Public LEO Catalog)</option>
              <option value="spacetrack">Space-Track (18th Space Defense)</option>
            </select>
          </div>

          <div className="flex items-center space-x-3 pt-3 sm:pt-4">
            <input
              type="checkbox"
              id="demo_mode"
              name="demo_mode"
              checked={form.demo_mode}
              onChange={(e) => updateField('demo_mode', e.target.checked)}
              className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500"
            />
            <label htmlFor="demo_mode" className="text-xs text-slate-200">
              <span className="font-semibold text-white block">Offline Demo Mode</span>
              <span className="text-slate-400 text-[11px]">
                Uses local deterministic catalog fixtures without external network calls
              </span>
            </label>
          </div>
        </div>
      </div>

      {/* Form Submission Actions */}
      <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-4">
        <button
          type="button"
          onClick={handleReset}
          disabled={isSubmitting}
          className="w-full sm:w-auto px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 bg-slate-900 border border-slate-800 rounded-md hover:border-slate-700 transition-colors"
        >
          Reset to Defaults
        </button>

        <div className="flex items-center space-x-3 w-full sm:w-auto">
          <button
            type="submit"
            disabled={!canSubmit}
            className={`w-full sm:w-auto px-6 py-2.5 text-sm font-semibold rounded-md shadow-sm transition-all flex items-center justify-center space-x-2 ${
              canSubmit
                ? 'bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer hover:shadow-indigo-500/25 shadow-md'
                : 'bg-slate-800 text-slate-500 border border-slate-700/50 cursor-not-allowed'
            }`}
          >
            {isSubmitting ? (
              <>
                <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Submitting Mission Plan...</span>
              </>
            ) : (
              <span>Launch Screening Run</span>
            )}
          </button>
        </div>
      </div>
    </form>
  )
}
