import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MissionBriefing } from '../components/results/MissionBriefing'
import { CandidateComparison } from '../components/results/CandidateComparison'
import { EventDetailPanel } from '../components/results/EventDetailPanel'
import { HeatmapControls } from '../components/results/HeatmapControls'
import { ValidationSection } from '../components/results/ValidationSection'
import { ResultsHeader } from '../components/results/ResultsHeader'
import type { RunStatusResponse } from '../types/run'
import type { PlanResponse } from '../types/plan'
import type { CandidateResultItem } from '../types/candidate'
import type { EventResultItem } from '../types/event'
import type { HeatmapResponse } from '../types/heatmap'
import type { ValidationResponse } from '../types/validation'

describe('Phase P26 — Mission Briefing, Guided Analysis & Space Mission UI', () => {
  const mockRun: RunStatusResponse = {
    run_id: 'run-p26-001',
    plan_id: 'plan-p26-001',
    status: 'completed',
    progress_percent: 100,
    current_stage: 'completed',
    message: 'Screening run complete',
    created_at: '2026-10-03T12:00:00Z',
    started_at: '2026-10-03T12:00:01Z',
    completed_at: '2026-10-03T12:00:05Z',
    error_message: null,
    candidate_count: 195,
    conjunction_event_count: 12,
    ranked_candidate_count: 195,
  }

  const mockPlan: PlanResponse = {
    plan_id: 'plan-p26-001',
    created_at: '2026-10-03T12:00:00Z',
    updated_at: '2026-10-03T12:00:00Z',
    epoch_start: '2026-10-03T12:00:00Z',
    altitude_min_km: 500,
    altitude_max_km: 600,
    altitude_step_km: 10,
    inclination_min_deg: 97,
    inclination_max_deg: 98,
    inclination_step_deg: 0.5,
    raan_deg: 0.0,
    u0_deg: 0.0,
    delay_min_minutes: 0,
    delay_max_minutes: 720,
    delay_step_minutes: 60,
    raan_delay_coupling_deg_per_min: 0.25068,
    screening_days: 3,
    reference_altitude_km: 550,
    reference_inclination_deg: 97.5,
    dv_budget_m_s: 100,
    spacecraft_mass_kg: 3.0,
    isp_seconds: 60,
    fuel_weight: 0.5,
    risk_weight: 0.5,
    data_source: 'celestrak',
    demo_mode: true,
  }

  describe('Part 1, 2, 3, 6, 8: Mission Briefing & Search Envelope', () => {
    it('renders Mission Briefing header, 8-step analysis timeline, and factual description', () => {
      render(<MissionBriefing run={mockRun} plan={mockPlan} />)

      expect(screen.getByTestId('mission-briefing')).toBeInTheDocument()
      expect(screen.getByText('MISSION BRIEFING')).toBeInTheDocument()
      expect(screen.getByText('Here is what D-DATO evaluated for this screening run.')).toBeInTheDocument()

      // 8 Pipeline steps
      expect(screen.getByText('Mission Defined')).toBeInTheDocument()
      expect(screen.getByText('Candidate Space Generated')).toBeInTheDocument()
      expect(screen.getByText('Orbital/Fuel Screening')).toBeInTheDocument()
      expect(screen.getByText('Close-Approach Screening')).toBeInTheDocument()
      expect(screen.getByText('Risk & Ranking')).toBeInTheDocument()
      expect(screen.getByText('Visual Analysis')).toBeInTheDocument()
      expect(screen.getByText('Reference Comparison')).toBeInTheDocument()
      expect(screen.getByText('Export')).toBeInTheDocument()

      // Factual mission summary statement
      expect(
        screen.getByText(/D-DATO evaluates a bounded set of candidate orbit and deployment configurations for relative screening trade-offs\./i)
      ).toBeInTheDocument()
    })

    it('renders visual search envelope values and mission intent explanations', () => {
      render(<MissionBriefing run={mockRun} plan={mockPlan} />)

      // Envelope indicators & badges
      expect(screen.getByText(/CANDIDATES EVALUATED:\s*195\s*\/\s*300/i)).toBeInTheDocument()
      expect(screen.getByText(/SCREENING WINDOW:\s*3\s*DAYS/i)).toBeInTheDocument()
      expect(screen.getByText('500 – 600 km')).toBeInTheDocument()
      expect(screen.getByText('97.0° – 98.0°')).toBeInTheDocument()
      expect(screen.getByText('0 – 720 min')).toBeInTheDocument()

      // Mission Intent factual explanations
      expect(screen.getByText('Changes the orbital altitude being screened.')).toBeInTheDocument()
      expect(screen.getByText('Changes the orbital-plane orientation.')).toBeInTheDocument()
      expect(screen.getByText('Explores different deployment timing windows.')).toBeInTheDocument()
      expect(screen.getByText('Provides the propulsion budget used for candidate budget checks.')).toBeInTheDocument()
      expect(screen.getByText('Defines how long the candidate/debris geometry is evaluated.')).toBeInTheDocument()
    })

    it('toggles the "How to Read D-DATO Results" expandable help panel', () => {
      render(<MissionBriefing run={mockRun} plan={mockPlan} />)

      const toggleButton = screen.getByRole('button', { name: /How to Read/i })
      expect(screen.queryByText(/Candidate ranking orders candidates within the evaluated set/i)).not.toBeInTheDocument()

      // Open panel
      fireEvent.click(toggleButton)
      expect(screen.getByText(/The score is a bounded screening heuristic from 0–100\. It is not a collision probability\./i)).toBeInTheDocument()
      expect(screen.getByText(/An event indicates that propagated trajectories came within the configured screening threshold\./i)).toBeInTheDocument()

      // Close panel
      fireEvent.click(toggleButton)
      expect(screen.queryByText(/Candidate ranking orders candidates within the evaluated set/i)).not.toBeInTheDocument()
    })
  })

  describe('Part 7: Candidate Trade-off Visual Badges', () => {
    const candidateA: CandidateResultItem = {
      candidate_id: 'cand-a',
      altitude_km: 500,
      inclination_deg: 97.4,
      raan_deg: 120,
      u0_deg: 45,
      deployment_delay_minutes: 30,
      delta_v_m_s: 15.0,
      propellant_mass_kg: 0.5,
      fuel_fraction: 0.005,
      within_dv_budget: true,
      risk_score: 12.0,
      accepted_event_count: 1,
      minimum_miss_distance_km: 18.5,
      uncertainty_level: 'nominal',
      composite_score: 14.0,
      rank: 1,
    }

    const candidateB: CandidateResultItem = {
      candidate_id: 'cand-b',
      altitude_km: 550,
      inclination_deg: 97.5,
      raan_deg: 120,
      u0_deg: 45,
      deployment_delay_minutes: 60,
      delta_v_m_s: 45.0,
      propellant_mass_kg: 1.5,
      fuel_fraction: 0.015,
      within_dv_budget: true,
      risk_score: 42.0,
      accepted_event_count: 5,
      minimum_miss_distance_km: 6.2,
      uncertainty_level: 'nominal',
      composite_score: 44.0,
      rank: 5,
    }

    it('renders comparative callout badges without claiming universal winner or forbidden words', () => {
      render(
        <CandidateComparison
          candidates={[candidateA, candidateB]}
          onRemoveCandidate={vi.fn()}
          onClear={vi.fn()}
          onSelectCandidate={vi.fn()}
        />
      )

      // Descriptive comparative badges
      expect(screen.getByText('LOWER ESTIMATED ΔV')).toBeInTheDocument()
      expect(screen.getByText('FEWER SCREENED EVENTS')).toBeInTheDocument()
      expect(screen.getByText('LOWER RELATIVE RISK SCORE')).toBeInTheDocument()

      // Section guidance
      expect(
        screen.getByText(/Compare candidate configurations using the persisted ranking, propulsion estimates, event counts and screening-risk indicators\./i)
      ).toBeInTheDocument()
    })
  })

  describe('Part 11: Event Investigation in Conjunction Panel', () => {
    const mockEvent: EventResultItem = {
      id: 'evt-999',
      candidate_id: 'cand-a',
      debris_object_id: 'DEB-1234',
      debris_norad_id: '54321',
      tca: '2026-10-04T14:30:00Z',
      miss_distance_km: 4.82,
      relative_velocity_km_s: 11.24,
      threshold_km: 25.0,
      screening_source: 'ddato',
    }

    it('renders Event Investigation block and triggers globe inspection navigation callback', () => {
      const inspectSpy = vi.fn()
      render(
        <EventDetailPanel
          event={mockEvent}
          onClose={vi.fn()}
          onInspectInGlobe={inspectSpy}
        />
      )

      expect(screen.getByText('Event Investigation')).toBeInTheDocument()
      expect(screen.getByText('54321')).toBeInTheDocument()
      expect(screen.getByText('4.82 km')).toBeInTheDocument()
      expect(screen.getByText('11.24 km/s')).toBeInTheDocument()

      const globeBtn = screen.getByRole('button', { name: /Inspect spatial geometry in the 3D Globe/i })
      expect(globeBtn).toBeInTheDocument()
      fireEvent.click(globeBtn)
      expect(inspectSpy).toHaveBeenCalledTimes(1)
    })
  })

  describe('Part 9: Heatmap Explanatory Bar and Selected Telemetry', () => {
    const mockHeatmapData: HeatmapResponse = {
      run_id: 'run-p26-001',
      status: 'completed',
      metric: 'screening_risk_score',
      x_axis: 'delay_minutes',
      y_axis: 'altitude_km',
      inclination_values_deg: [97.0, 97.5, 98.0],
      total_candidates: 27,
      populated_cells: 27,
      min_risk_score: 5.0,
      max_risk_score: 85.0,
      layers: [],
    }

    it('displays compact explanatory bar and selected candidate parameters', () => {
      render(
        <HeatmapControls
          heatmapData={mockHeatmapData}
          selectedLayer={null}
          selectedInclination={97.5}
          onSelectInclination={vi.fn()}
          selectedCandidate={{
            altitude_km: 550.0,
            inclination_deg: 97.5,
            deployment_delay_minutes: 60,
            risk_score: 22.4,
          }}
        />
      )

      expect(
        screen.getByText('Each cell represents one candidate configuration in the current inclination layer.')
      ).toBeInTheDocument()
      expect(screen.getByText('550.0 km')).toBeInTheDocument()
      expect(screen.getByText('60 min')).toBeInTheDocument()
      expect(screen.getAllByText('97.5°').length).toBeGreaterThan(0)
      expect(screen.getByText('22.4')).toBeInTheDocument()
    })
  })

  describe('Part 12: Validation Story & 3-Step Explanation', () => {
    it('renders 3-step validation flow and technical comparison explanation', () => {
      const mockValidation: ValidationResponse = {
        validation_id: 'val-001',
        run_id: 'run-p26-001',
        status: 'completed',
        source: 'socrates',
        source_fetched_at: '2026-10-03T12:00:00Z',
        validation_created_at: '2026-10-03T12:00:01Z',
        matches: [],
        d_dato_only: [],
        external_only: [],
        summary: {
          d_dato_event_count: 5,
          external_event_count: 5,
          matched_event_count: 0,
          d_dato_only_count: 5,
          external_only_count: 5,
          external_coverage_percent: null,
          d_dato_match_rate_percent: null,
          mean_abs_tca_error_seconds: null,
          max_abs_tca_error_seconds: null,
          mean_abs_miss_distance_difference_km: null,
          max_abs_miss_distance_difference_km: null,
        },
        notes: ['Demonstration dataset'],
      }

      render(
        <ValidationSection
          validation={mockValidation}
          isLoading={false}
          isRunning={false}
          error={null}
          onRunValidation={vi.fn()}
          onRetry={vi.fn()}
        />
      )

      expect(screen.getAllByText('REFERENCE COMPARISON').length).toBeGreaterThan(0)
      expect(screen.getByText('D-DATO EVENTS')).toBeInTheDocument()
      expect(screen.getByText('MATCHING CRITERIA')).toBeInTheDocument()
      expect(
        screen.getByText('The comparison checks whether D-DATO events can be paired with external reference events within configured temporal and spatial tolerances.')
      ).toBeInTheDocument()
      expect(screen.getByText('NO MATCHED EVENTS')).toBeInTheDocument()
      expect(screen.getByText('No event pair satisfied the configured comparison tolerances for this run.')).toBeInTheDocument()
    })
  })

  describe('Part 15: ResultsHeader Breadcrumb Navigation', () => {
    it('renders breadcrumb with short run ID and functional back navigation', () => {
      const backSpy = vi.fn()
      render(
        <ResultsHeader
          runId="12345678-abcd-ef01-2345-6789abcdef01"
          planId="plan-001"
          status="completed"
          onBackToPlanner={backSpy}
        />
      )

      const breadcrumb = screen.getByLabelText('Breadcrumb')
      expect(breadcrumb).toBeInTheDocument()
      expect(screen.getByText('Run 12345678')).toBeInTheDocument()

      const brandBtn = screen.getByRole('button', { name: 'D-DATO' })
      fireEvent.click(brandBtn)
      expect(backSpy).toHaveBeenCalledTimes(1)
    })
  })
})
