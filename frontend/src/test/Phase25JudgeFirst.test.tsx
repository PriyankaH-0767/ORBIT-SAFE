import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PlannerHero } from '../components/planner/PlannerHero'
import { MissionPresets } from '../components/planner/MissionPresets'
import { CandidateComparison } from '../components/results/CandidateComparison'
import { DataProvenanceStrip } from '../components/results/DataProvenanceStrip'
import { EventDetailPanel } from '../components/results/EventDetailPanel'
import { ValidationSummaryPanel } from '../components/results/ValidationSummaryPanel'
import { CandidateDetailPanel } from '../components/results/CandidateDetailPanel'
import type { CandidateResultItem } from '../types/candidate'
import type { EventResultItem } from '../types/event'
import type { ValidationSummary } from '../types/validation'

describe('Phase P25 — Judge-First Mission-Control UI Upgrades', () => {
  describe('Section A: PlannerHero', () => {
    it('renders D-DATO title, explanatory sentence, 7 capabilities, and 6-stage workflow', () => {
      render(<PlannerHero />)

      // Title & Explanatory sentence
      expect(screen.getByText('D-DATO')).toBeInTheDocument()
      expect(
        screen.getByText('Debris-Aware Orbit & Deployment-Window Planner')
      ).toBeInTheDocument()
      expect(
        screen.getByText('Screen candidate CubeSat deployment windows before detailed mission design.')
      ).toBeInTheDocument()

      // 7 capabilities
      expect(screen.getByText('Generate candidate orbit/deployment combinations')).toBeInTheDocument()
      expect(screen.getByText('Estimate propulsion demand')).toBeInTheDocument()
      expect(screen.getByText('Screen close approaches')).toBeInTheDocument()
      expect(screen.getByText('Calculate bounded screening risk')).toBeInTheDocument()
      expect(screen.getByText('Visualize candidate trade-offs')).toBeInTheDocument()
      expect(screen.getByText('Validate against reference data')).toBeInTheDocument()
      expect(screen.getByText('Export analysis')).toBeInTheDocument()

      // 6-step visual workflow strip
      expect(screen.getByText('DEFINE MISSION')).toBeInTheDocument()
      expect(screen.getByText('SCREEN CANDIDATES')).toBeInTheDocument()
      expect(screen.getByText('COMPARE RESULTS')).toBeInTheDocument()
      expect(screen.getByText('VISUALIZE')).toBeInTheDocument()
      expect(screen.getByText('VALIDATE')).toBeInTheDocument()
      expect(screen.getByText('EXPORT')).toBeInTheDocument()
    })
  })

  describe('Section B & C: MissionPresets', () => {
    it('renders 2-minute demo button and all 3 predefined presets', () => {
      const handleSelectPreset = vi.fn()
      const handleTryDemo = vi.fn()
      render(
        <MissionPresets
          activePresetId="sso_demo"
          onSelectPreset={handleSelectPreset}
          onTryDemo={handleTryDemo}
        />
      )

      // Prominent Demo button
      const demoBtn = screen.getByRole('button', { name: /try 2-minute demo/i })
      expect(demoBtn).toBeInTheDocument()
      fireEvent.click(demoBtn)
      expect(handleTryDemo).toHaveBeenCalledTimes(1)

      // Presets
      expect(screen.getByText('High-Inclination LEO / SSO-Style Screening')).toBeInTheDocument()
      expect(screen.getByText('Low LEO Screening')).toBeInTheDocument()
      expect(screen.getAllByText('Custom Mission').length).toBeGreaterThanOrEqual(1)
    })
  })

  describe('Section G: CandidateExplanation ("Why is this candidate ranked here?")', () => {
    it('displays explanation panel with persisted values without claiming safest or optimal', () => {
      const mockCandidate: CandidateResultItem = {
        candidate_id: 'cand-001',
        altitude_km: 550,
        inclination_deg: 97.5,
        raan_deg: 180,
        u0_deg: 0,
        deployment_delay_minutes: 30,
        delta_v_m_s: 45.2,
        propellant_mass_kg: 3.5,
        fuel_fraction: 0.035,
        within_dv_budget: true,
        risk_score: 18.4,
        composite_score: 0.245,
        rank: 1,
        accepted_event_count: 0,
        minimum_miss_distance_km: null,
      }

      render(<CandidateDetailPanel candidate={mockCandidate} onClose={vi.fn()} />)

      expect(screen.getByText('Why is this candidate ranked here?')).toBeInTheDocument()
      expect(screen.getByText(/relatively low/i)).toBeInTheDocument()
      expect(screen.getByText(/estimated propulsion demand within the configured budget/i)).toBeInTheDocument()
      expect(screen.getByText(/No close-approach events were screened/i)).toBeInTheDocument()

      // Audit: No forbidden claims
      const html = document.body.innerHTML.toLowerCase()
      expect(html).not.toContain('safest')
      expect(html).not.toContain('optimal')
      expect(html).not.toContain('flight approved')
      expect(html).not.toContain('collision probability')
    })
  })

  describe('Section H: CandidateComparison', () => {
    it('renders comparison matrix for up to 3 candidates and handles remove/clear', () => {
      const candidates: CandidateResultItem[] = [
        {
          candidate_id: 'cand-001',
          altitude_km: 500,
          inclination_deg: 97.4,
          raan_deg: 120,
          u0_deg: 0,
          deployment_delay_minutes: 0,
          delta_v_m_s: 30.5,
          propellant_mass_kg: 2.1,
          fuel_fraction: 0.021,
          within_dv_budget: true,
          risk_score: 12.0,
          rank: 1,
          accepted_event_count: 0,
        },
        {
          candidate_id: 'cand-002',
          altitude_km: 550,
          inclination_deg: 97.6,
          raan_deg: 125,
          u0_deg: 0,
          deployment_delay_minutes: 60,
          delta_v_m_s: 55.0,
          propellant_mass_kg: 4.2,
          fuel_fraction: 0.042,
          within_dv_budget: true,
          risk_score: 25.5,
          rank: 2,
          accepted_event_count: 1,
          minimum_miss_distance_km: 12.4,
        },
      ]

      const handleRemove = vi.fn()
      const handleClear = vi.fn()

      render(
        <CandidateComparison
          candidates={candidates}
          onRemoveCandidate={handleRemove}
          onClear={handleClear}
        />
      )

      expect(screen.getByText(/Candidate Trade-Off Comparison/i)).toBeInTheDocument()
      expect(screen.getAllByText('Rank #1').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Rank #2').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('500.0 km')).toBeInTheDocument()
      expect(screen.getByText('550.0 km')).toBeInTheDocument()

      const clearBtn = screen.getByRole('button', { name: /Clear All/i })
      fireEvent.click(clearBtn)
      expect(handleClear).toHaveBeenCalledTimes(1)
    })
  })

  describe('Section K: Conjunction Drawer Copy', () => {
    it('renders spatial inspection in 3D globe copy instead of future phase wording', () => {
      const mockEvent: EventResultItem = {
        id: 'evt-101',
        candidate_id: 'cand-001',
        debris_object_id: 'deb-501',
        tca: '2026-10-05T14:30:00Z',
        miss_distance_km: 8.52,
        relative_velocity_km_s: 14.1,
        threshold_km: 25.0,
        screening_source: 'TLE',
      }

      render(<EventDetailPanel event={mockEvent} onClose={vi.fn()} />)

      expect(
        screen.getByText(/This close-approach event can be inspected spatially in the 3D Globe section./i)
      ).toBeInTheDocument()
      expect(
        screen.queryByText(/A future 3D visualization phase will utilize this event geometry/i)
      ).not.toBeInTheDocument()
    })
  })

  describe('Section L: Validation UX Zero-Match Message', () => {
    it('displays informative zero-match message when matched_event_count is 0', () => {
      const summary: ValidationSummary = {
        d_dato_event_count: 5,
        external_event_count: 10,
        matched_event_count: 0,
        d_dato_only_count: 5,
        external_only_count: 10,
        external_coverage_percent: null,
        d_dato_match_rate_percent: null,
        mean_abs_tca_error_seconds: null,
        max_abs_tca_error_seconds: null,
        mean_abs_miss_distance_difference_km: null,
        max_abs_miss_distance_difference_km: null,
      }

      render(<ValidationSummaryPanel summary={summary} />)

      expect(
        screen.getByText('No matching conjunction events were found within the configured comparison tolerances.')
      ).toBeInTheDocument()
      expect(
        screen.getByText('This demo produced no paired events suitable for numerical difference metrics.')
      ).toBeInTheDocument()
    })
  })

  describe('Section M: Data Provenance Strip', () => {
    it('renders catalog source, offline execution mode, reference frame, and epoch', () => {
      render(
        <DataProvenanceStrip
          run={{
            run_id: 'run-001',
            plan_id: 'plan-001',
            status: 'completed',
            progress_percent: 100,
            current_stage: null,
            message: null,
            created_at: '2026-10-03T10:00:00Z',
            started_at: null,
            completed_at: null,
            error_message: null,
            candidate_count: 195,
            conjunction_event_count: 14,
            ranked_candidate_count: 195,
          }}
        />
      )

      expect(screen.getByTestId('data-provenance-strip')).toBeInTheDocument()
      expect(screen.getByText('CelesTrak (Public LEO Catalog)')).toBeInTheDocument()
      expect(screen.getByText('Deterministic Offline Demo Mode')).toBeInTheDocument()
      expect(screen.getByText(/TEME/)).toBeInTheDocument()
    })
  })
})
