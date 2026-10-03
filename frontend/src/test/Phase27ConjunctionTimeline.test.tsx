import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { ConjunctionTimeline } from '../components/results/ConjunctionTimeline'
import { PlannerHero } from '../components/planner/PlannerHero'
import { MissionPresets } from '../components/planner/MissionPresets'
import { ResultsHeader } from '../components/results/ResultsHeader'
import type { EventResultItem } from '../types/event'
import type { PlanResponse } from '../types/plan'
import { MISSION_PRESETS } from '../types/presets'

const mockEvents: EventResultItem[] = [
  {
    id: 'evt-001',
    candidate_id: 'cand-alpha',
    debris_object_id: 'deb-001',
    debris_norad_id: '700001',
    tca: '2026-10-03T17:03:55.000Z',
    miss_distance_km: 21.95,
    relative_velocity_km_s: 14.54,
    threshold_km: 25.0,
    screening_source: 'ddato',
  },
  {
    id: 'evt-002',
    candidate_id: 'cand-beta',
    debris_object_id: 'deb-001',
    debris_norad_id: '700001',
    tca: '2026-10-04T12:12:39.000Z',
    miss_distance_km: 10.40,
    relative_velocity_km_s: 11.91,
    threshold_km: 25.0,
    screening_source: 'ddato',
  },
  {
    id: 'evt-003',
    candidate_id: 'cand-alpha',
    debris_object_id: 'deb-002',
    debris_norad_id: '25544',
    tca: '2026-10-05T14:34:24.000Z',
    miss_distance_km: 12.52,
    relative_velocity_km_s: 13.90,
    threshold_km: 25.0,
    screening_source: 'ddato',
  },
]

const mockPlan: PlanResponse = {
  plan_id: 'plan-123',
  epoch_start: '2026-10-02T12:00:00Z',
  altitude_min_km: 500.0,
  altitude_max_km: 600.0,
  altitude_step_km: 25.0,
  inclination_min_deg: 97.0,
  inclination_max_deg: 98.0,
  inclination_step_deg: 0.5,
  raan_deg: 0.0,
  u0_deg: 0.0,
  delay_min_minutes: 0.0,
  delay_max_minutes: 720.0,
  delay_step_minutes: 60.0,
  raan_delay_coupling_deg_per_min: 0.25068,
  screening_days: 3.0,
  reference_altitude_km: 550.0,
  reference_inclination_deg: 97.5,
  dv_budget_m_s: 100.0,
  spacecraft_mass_kg: 3.0,
  isp_seconds: 60.0,
  fuel_weight: 0.4,
  risk_weight: 0.6,
  data_source: 'celestrak',
  demo_mode: true,
  created_at: '2026-10-02T12:00:00Z',
  updated_at: '2026-10-02T12:00:00Z',
}

describe('Phase P27 — Temporal Conjunction Intelligence & Demo Experience', () => {
  describe('Part 1, 5, 15: ConjunctionTimeline Temporal Rendering', () => {
    it('renders temporal screening window context and duration from plan data', () => {
      render(
        <ConjunctionTimeline
          events={mockEvents}
          plan={mockPlan}
          onSelectEvent={vi.fn()}
        />
      )

      expect(screen.getByText('CONJUNCTION TIMELINE')).toBeInTheDocument()
      expect(screen.getByText(/Temporal Screening Dispersion/i)).toBeInTheDocument()
      expect(screen.getByText(/3.0 Days/i)).toBeInTheDocument()
      expect(screen.getByText(/Markers indicate screened close-approach events at their persisted TCA/i)).toBeInTheDocument()
    })

    it('calculates and displays event density summary metrics directly from persisted event attributes', () => {
      render(
        <ConjunctionTimeline
          events={mockEvents}
          plan={mockPlan}
          onSelectEvent={vi.fn()}
        />
      )

      const summary = screen.getByTestId('event-density-summary')
      expect(summary).toBeInTheDocument()
      expect(within(summary).getByText('3')).toBeInTheDocument() // 3 total events
      expect(within(summary).getByText(/10.40/)).toBeInTheDocument() // closest miss distance
    })

    it('renders timeline nodes with NORAD ID, miss distance, relative velocity, and formatted UTC TCA', () => {
      render(
        <ConjunctionTimeline
          events={mockEvents}
          plan={mockPlan}
          onSelectEvent={vi.fn()}
        />
      )

      expect(screen.getAllByText(/NORAD #700001/i).length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText(/NORAD #25544/i)).toBeInTheDocument()
      expect(screen.getByText(/21.95 km/i)).toBeInTheDocument()
      expect(screen.getByText(/10.40 km/i)).toBeInTheDocument()
      expect(screen.getByText(/14.54 km\/s/i)).toBeInTheDocument()
    })
  })

  describe('Part 2, 14, 17: Timeline Interaction, Globe Sync & Keyboard Accessibility', () => {
    it('triggers onSelectEvent when an event node is clicked', () => {
      const handleSelectEvent = vi.fn()
      render(
        <ConjunctionTimeline
          events={mockEvents}
          plan={mockPlan}
          onSelectEvent={handleSelectEvent}
        />
      )

      const eventNode = screen.getByLabelText(/Conjunction event TCA.*NORAD 25544/i)
      fireEvent.click(eventNode)
      expect(handleSelectEvent).toHaveBeenCalledWith(mockEvents[2])
    })

    it('supports keyboard activation via Enter and Space with focusable elements', () => {
      const handleSelectEvent = vi.fn()
      render(
        <ConjunctionTimeline
          events={mockEvents}
          plan={mockPlan}
          onSelectEvent={handleSelectEvent}
        />
      )

      const eventNode = screen.getByLabelText(/Conjunction event TCA.*NORAD 25544/i)
      eventNode.focus()
      fireEvent.keyDown(eventNode, { key: 'Enter' })
      expect(handleSelectEvent).toHaveBeenCalledTimes(1)

      fireEvent.keyDown(eventNode, { key: ' ' })
      expect(handleSelectEvent).toHaveBeenCalledTimes(2)
    })

    it('renders "Inspect spatial geometry in 3D Globe" action when event is selected', () => {
      const handleInspectInGlobe = vi.fn()
      render(
        <ConjunctionTimeline
          events={mockEvents}
          selectedEventId="evt-002"
          plan={mockPlan}
          onSelectEvent={vi.fn()}
          onInspectInGlobe={handleInspectInGlobe}
        />
      )

      const inspectBtn = screen.getByRole('button', { name: /Inspect spatial geometry in 3D Globe/i })
      expect(inspectBtn).toBeInTheDocument()
      fireEvent.click(inspectBtn)
      expect(handleInspectInGlobe).toHaveBeenCalledWith(mockEvents[1])
    })
  })

  describe('Part 3 & 4: Timeline Filters and Empty Timeline', () => {
    it('filters timeline by selected candidate when Candidate filter is clicked', () => {
      render(
        <ConjunctionTimeline
          events={mockEvents}
          selectedCandidateId="cand-beta"
          plan={mockPlan}
          onSelectEvent={vi.fn()}
        />
      )

      const candidateFilterBtn = screen.getByRole('button', { name: /Selected Candidate/i })
      fireEvent.click(candidateFilterBtn)

      // Only cand-beta event should be visible
      expect(screen.getByText(/10.40 km/i)).toBeInTheDocument()
      expect(screen.queryByText(/21.95 km/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/NORAD #25544/i)).not.toBeInTheDocument()
    })

    it('renders conservative non-operational message when zero events are present', () => {
      render(
        <ConjunctionTimeline
          events={[]}
          plan={mockPlan}
          onSelectEvent={vi.fn()}
        />
      )

      expect(screen.getByText('NO SCREENED CLOSE-APPROACH EVENTS')).toBeInTheDocument()
      expect(
        screen.getByText(/No conjunction events were identified within the configured screening threshold and time window/i)
      ).toBeInTheDocument()
      expect(screen.queryByText(/safe|optimal|guaranteed/i)).not.toBeInTheDocument()
    })
  })

  describe('Part 8, 9, 10, 11, 12: Problem/Solution Hero, Presets & Screening Mode', () => {
    it('renders "THE EARLY-STAGE CHALLENGE" and Mission Flow Strip in PlannerHero', () => {
      render(<PlannerHero />)

      expect(screen.getByText('THE EARLY-STAGE CHALLENGE')).toBeInTheDocument()
      expect(screen.getByText(/CubeSat teams may need to compare multiple orbit and deployment configurations/i)).toBeInTheDocument()
      expect(screen.getByText('Candidate Orbit Configurations')).toBeInTheDocument()
      expect(screen.getByText('Deployment Windows')).toBeInTheDocument()
      expect(screen.getByText('Propulsion Demand')).toBeInTheDocument()

      // Mission Screening Lifecycle Flow
      expect(screen.getByText('Mission Screening Lifecycle Flow')).toBeInTheDocument()
      expect(screen.getByText('DEFINE MISSION')).toBeInTheDocument()
      expect(screen.getByText('SCREEN CANDIDATES')).toBeInTheDocument()
      expect(screen.getByText('COMPARE RESULTS')).toBeInTheDocument()
    })

    it('displays persistent Screening Mode indicator with offline demo details', () => {
      render(<PlannerHero />)
      const indicator = screen.getByTestId('screening-mode-indicator')
      expect(indicator).toBeInTheDocument()
      expect(indicator).toHaveTextContent(/Screening Mode:\s*Offline Demo/i)
      expect(indicator).toHaveTextContent(/CelesTrak/i)
    })

    it('audits preset terminology to High-Inclination LEO / SSO-Style Screening without false Sun-sync claims', () => {
      expect(MISSION_PRESETS[0].name).toBe('High-Inclination LEO / SSO-Style Screening')
      expect(MISSION_PRESETS[0].name).not.toBe('Sun-Synchronous LEO')
    })

    it('audits demo button label to START GUIDED DEMO in MissionPresets', () => {
      render(
        <MissionPresets
          activePresetId="sso_demo"
          onSelectPreset={vi.fn()}
          onTryDemo={vi.fn()}
        />
      )

      expect(screen.getByRole('button', { name: /start guided demo/i })).toBeInTheDocument()
      expect(screen.getByText(/~90s Screening Run/i)).toBeInTheDocument()
    })

    it('renders screening mode badge on ResultsHeader', () => {
      render(
        <ResultsHeader
          runId="run-test-456"
          planId="plan-test-123"
          status="completed"
          demoMode={true}
          dataSource="celestrak"
          onBackToPlanner={vi.fn()}
        />
      )

      const indicator = screen.getByTestId('results-screening-mode-indicator')
      expect(indicator).toBeInTheDocument()
      expect(indicator).toHaveTextContent(/SCREENING MODE:\s*OFFLINE DEMO/i)
      expect(indicator).toHaveTextContent(/Source:\s*CELESTRAK/i)
    })
  })
})
