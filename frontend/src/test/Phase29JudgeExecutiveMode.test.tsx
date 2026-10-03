import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { JudgeExecutiveSummary } from '../components/results/JudgeExecutiveSummary'
import { ResultsHeader } from '../components/results/ResultsHeader'
import { PlannerHero } from '../components/planner/PlannerHero'
import type { PlanResponse } from '../types/plan'
import type { RunStatusResponse } from '../types/run'
import type { EventResultItem } from '../types/event'

const mockPlan: PlanResponse = {
  plan_id: 'plan-judge-001',
  created_at: '2026-10-03T12:00:00Z',
  updated_at: '2026-10-03T12:00:00Z',
  epoch_start: '2026-10-03T00:00:00Z',
  altitude_min_km: 500.0,
  altitude_max_km: 600.0,
  altitude_step_km: 25.0,
  inclination_min_deg: 97.0,
  inclination_max_deg: 98.0,
  inclination_step_deg: 0.5,
  raan_deg: 0.0,
  u0_deg: 0.0,
  delay_min_minutes: 0.0,
  delay_max_minutes: 360.0,
  delay_step_minutes: 60.0,
  raan_delay_coupling_deg_per_min: 0.25068,
  screening_days: 3.0,
  reference_altitude_km: 550.0,
  reference_inclination_deg: 97.5,
  dv_budget_m_s: 100.0,
  spacecraft_mass_kg: 3.0,
  isp_seconds: 60.0,
  fuel_weight: 0.5,
  risk_weight: 0.5,
  data_source: 'celestrak',
  demo_mode: true,
}

const mockRun: RunStatusResponse = {
  run_id: 'run-judge-001',
  plan_id: 'plan-judge-001',
  status: 'completed',
  progress_percent: 100,
  current_stage: null,
  message: 'Screening evaluation complete.',
  created_at: '2026-10-03T12:00:00Z',
  started_at: '2026-10-03T12:00:01Z',
  completed_at: '2026-10-03T12:01:32Z',
  error_message: null,
  candidate_count: 2,
  conjunction_event_count: 3,
  ranked_candidate_count: 2,
}

const mockEvents: EventResultItem[] = [
  {
    id: 'evt-001',
    candidate_id: 'cand-001',
    debris_object_id: 'deb-001',
    debris_norad_id: '25544',
    tca: '2026-10-04T08:15:30Z',
    miss_distance_km: 12.45,
    relative_velocity_km_s: 14.2,
    threshold_km: 25.0,
    screening_source: 'ddato',
  },
  {
    id: 'evt-002',
    candidate_id: 'cand-002',
    debris_object_id: 'deb-002',
    debris_norad_id: '40001',
    tca: '2026-10-05T14:22:10Z',
    miss_distance_km: 4.82,
    relative_velocity_km_s: 11.8,
    threshold_km: 25.0,
    screening_source: 'ddato',
  },
]

describe('Phase P29 — Judge View, Executive Presentation UX & Demo Hardening', () => {
  describe('JudgeExecutiveSummary Component', () => {
    it('renders mission summary, compact metrics, and early-stage screening notice', () => {
      render(
        <JudgeExecutiveSummary
          run={mockRun}
          plan={mockPlan}
          candidateTotal={195}
          eventTotal={19}
          events={mockEvents}
          isDemoActive={true}
        />
      )

      expect(screen.getByTestId('demo-executive-summary')).toBeInTheDocument()
      expect(screen.getByText(/DEMO OVERVIEW • D-DATO MISSION SUMMARY/i)).toBeInTheDocument()
      expect(screen.getByText(/SIH 2026 • PS 26209/i)).toBeInTheDocument()
      expect(
        screen.getByText(
          /D-DATO provides early-stage screening of candidate orbit and deployment configurations using persisted orbital-data and screening results./i
        )
      ).toBeInTheDocument()

      // Compact metrics
      expect(screen.getByText('500–600 km')).toBeInTheDocument()
      expect(screen.getByText('195')).toBeInTheDocument()
      expect(screen.getByText('19')).toBeInTheDocument()
      expect(screen.getByText('3.0')).toBeInTheDocument()
      expect(screen.getByText('Offline Demo')).toBeInTheDocument()
      expect(screen.getByText('CELESTRAK')).toBeInTheDocument()
    })

    it('renders "WHY D-DATO?" and "HOW D-DATO WORKS" 6-stage pipeline', () => {
      render(
        <JudgeExecutiveSummary
          run={mockRun}
          plan={mockPlan}
          candidateTotal={195}
          eventTotal={19}
          events={mockEvents}
          isDemoActive={true}
        />
      )

      expect(screen.getByText('WHY D-DATO?')).toBeInTheDocument()
      expect(
        screen.getByText(
          /Early mission concepts may contain multiple feasible orbit and deployment configurations. D-DATO provides a bounded screening workflow for comparing propulsion demand, close-approach events and relative screening indicators before detailed mission design./i
        )
      ).toBeInTheDocument()

      // 6 stages
      expect(screen.getByText('DEFINE')).toBeInTheDocument()
      expect(screen.getByText('SCREEN')).toBeInTheDocument()
      expect(screen.getByText('COMPARE')).toBeInTheDocument()
      expect(screen.getByText('VISUALIZE')).toBeInTheDocument()
      expect(screen.getByText('VALIDATE')).toBeInTheDocument()
      expect(screen.getByText('EXPORT')).toBeInTheDocument()
    })

    it('renders factual SCREENING TAKEAWAYS without unscientific optimality claims', () => {
      render(
        <JudgeExecutiveSummary
          run={mockRun}
          plan={mockPlan}
          candidateTotal={195}
          eventTotal={19}
          events={mockEvents}
          isDemoActive={true}
        />
      )

      expect(screen.getByText('SCREENING TAKEAWAYS')).toBeInTheDocument()
      expect(screen.getByText(/195 candidate configurations/i)).toBeInTheDocument()
      expect(screen.getByText(/19 screened close-approach events/i)).toBeInTheDocument()
      expect(
        screen.getByText(
          /Candidate results can be compared using delta-v, event count, miss distance and screening-risk indicators./i
        )
      ).toBeInTheDocument()
      expect(
        screen.getByText(/3D geometry is available for spatial inspection in the pseudofixed Cesium globe./i)
      ).toBeInTheDocument()
      expect(
        screen.getByText(/Reference comparison is available using the configured external dataset./i)
      ).toBeInTheDocument()
    })

    it('renders temporal conjunction highlights from persisted events', () => {
      render(
        <JudgeExecutiveSummary
          run={mockRun}
          plan={mockPlan}
          candidateTotal={195}
          eventTotal={2}
          events={mockEvents}
          isDemoActive={true}
        />
      )

      expect(screen.getByText(/TEMPORAL CONJUNCTION HIGHLIGHTS:/i)).toBeInTheDocument()
      expect(
        screen.getByText(/Events are shown at their persisted TCA across the screening window./i)
      ).toBeInTheDocument()
      expect(screen.getByText('4.82 km')).toBeInTheDocument() // Closest screened approach
    })
  })

  describe('ResultsHeader View Mode Switcher', () => {
    it('renders Demo View and Technical View buttons with active state', () => {
      const onViewModeChange = vi.fn()
      const onToggleDemoMode = vi.fn()

      render(
        <ResultsHeader
          runId="run-judge-001"
          planId="plan-judge-001"
          status="completed"
          demoMode={true}
          viewMode="demo"
          onViewModeChange={onViewModeChange}
          isDemoActive={true}
          onToggleDemoMode={onToggleDemoMode}
          onBackToPlanner={vi.fn()}
        />
      )

      expect(screen.getByTestId('view-mode-selector')).toBeInTheDocument()
      const demoViewBtn = screen.getByTestId('toggle-view-demo')
      const techBtn = screen.getByTestId('toggle-view-technical')
      const demoModeBtn = screen.getByTestId('toggle-demo-mode')

      expect(demoViewBtn).toHaveAttribute('aria-pressed', 'true')
      expect(demoViewBtn).toHaveTextContent('DEMO VIEW')
      expect(techBtn).toHaveAttribute('aria-pressed', 'false')
      expect(techBtn).toHaveTextContent('TECHNICAL VIEW')
      expect(screen.getByText(/DEMO MODE: ON/i)).toBeInTheDocument()

      fireEvent.click(techBtn)
      expect(onViewModeChange).toHaveBeenCalledWith('technical')

      fireEvent.click(demoModeBtn)
      expect(onToggleDemoMode).toHaveBeenCalled()
    })
  })

  describe('PlannerHero Landing Experience', () => {
    it('renders instant guided demo CTA with DEMO READY badge in the first viewport', () => {
      const onStartDemo = vi.fn()

      render(
        <PlannerHero
          onStartDemo={onStartDemo}
          isDemoLoading={false}
          isDemoReady={true}
        />
      )

      const demoBtn = screen.getByTestId('hero-guided-demo-btn')
      expect(demoBtn).toBeInTheDocument()
      expect(within(demoBtn).getByText('START GUIDED DEMO')).toBeInTheDocument()
      expect(within(demoBtn).getByText('DEMO READY')).toBeInTheDocument()

      fireEvent.click(demoBtn)
      expect(onStartDemo).toHaveBeenCalledTimes(1)
    })

    it('renders loading state on hero demo button when isDemoLoading is true', () => {
      render(
        <PlannerHero
          onStartDemo={vi.fn()}
          isDemoLoading={true}
          isDemoReady={true}
        />
      )

      expect(screen.getByText('LOADING DEMO…')).toBeInTheDocument()
    })
  })
})
