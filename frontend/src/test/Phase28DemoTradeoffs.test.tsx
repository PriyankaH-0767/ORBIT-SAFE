import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { CandidateComparison } from '../components/results/CandidateComparison'
import { CandidateTradeoffExplorer } from '../components/results/CandidateTradeoffExplorer'
import { ResultsHeader } from '../components/results/ResultsHeader'
import { GlobeLegend } from '../components/results/GlobeLegend'
import { MissionPresets } from '../components/planner/MissionPresets'
import type { CandidateResultItem } from '../types/candidate'
import Plotly from 'plotly.js-dist-min'

vi.mock('plotly.js-dist-min', () => ({
  default: {
    react: vi.fn().mockImplementation(() => Promise.resolve()),
    purge: vi.fn(),
    Plots: {
      resize: vi.fn(),
    },
  },
}))

const mockCandidates: CandidateResultItem[] = [
  {
    candidate_id: 'cand-001-alpha',
    rank: 1,
    altitude_km: 550.0,
    inclination_deg: 97.4,
    raan_deg: 0.0,
    u0_deg: 0.0,
    deployment_delay_minutes: 60.0,
    delta_v_m_s: 32.5,
    propellant_mass_kg: 0.45,
    fuel_fraction: 0.035,
    within_dv_budget: true,
    risk_score: 14.2,
    accepted_event_count: 0,
    minimum_miss_distance_km: null,
    uncertainty_level: 'nominal',
  },
  {
    candidate_id: 'cand-002-beta',
    rank: 2,
    altitude_km: 575.0,
    inclination_deg: 97.8,
    raan_deg: 0.0,
    u0_deg: 0.0,
    deployment_delay_minutes: 120.0,
    delta_v_m_s: 48.0,
    propellant_mass_kg: 0.68,
    fuel_fraction: 0.052,
    within_dv_budget: true,
    risk_score: 28.5,
    accepted_event_count: 2,
    minimum_miss_distance_km: 18.4,
    uncertainty_level: 'nominal',
  },
  {
    candidate_id: 'cand-003-gamma',
    rank: 3,
    altitude_km: 600.0,
    inclination_deg: 98.2,
    raan_deg: 0.0,
    u0_deg: 0.0,
    deployment_delay_minutes: 180.0,
    delta_v_m_s: 75.2,
    propellant_mass_kg: 1.15,
    fuel_fraction: 0.088,
    within_dv_budget: false,
    risk_score: 45.0,
    accepted_event_count: 5,
    minimum_miss_distance_km: 8.2,
    uncertainty_level: 'moderate',
  },
]

describe('Phase P28 — Candidate Trade-Off Explorer & Multi-Orbit Mission View', () => {
  describe('CandidateComparison Component (Trade-Off Explorer)', () => {
    it('returns null when candidates list is empty', () => {
      const { container } = render(
        <CandidateComparison
          candidates={[]}
          onRemoveCandidate={vi.fn()}
          onClear={vi.fn()}
        />
      )
      expect(container.firstChild).toBeNull()
    })

    it('renders side-by-side comparison table for selected candidates', () => {
      render(
        <CandidateComparison
          candidates={[mockCandidates[0], mockCandidates[1]]}
          onRemoveCandidate={vi.fn()}
          onClear={vi.fn()}
        />
      )

      expect(screen.getByTestId('candidate-comparison')).toBeInTheDocument()
      expect(screen.getByText(/Candidate Trade-Off Comparison \(2 \/ 3 selected\)/i)).toBeInTheDocument()
      expect(screen.getAllByText('Rank #1').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Rank #2').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('550.0 km')).toBeInTheDocument()
      expect(screen.getByText('575.0 km')).toBeInTheDocument()
      expect(screen.getByText('32.50 m/s')).toBeInTheDocument()
      expect(screen.getByText('48.00 m/s')).toBeInTheDocument()
    })

    it('computes and highlights relative factual trade-off badges', () => {
      render(
        <CandidateComparison
          candidates={[mockCandidates[0], mockCandidates[1]]}
          onRemoveCandidate={vi.fn()}
          onClear={vi.fn()}
        />
      )

      // Candidate 1 has lower delta-v, lower risk, and fewer events
      expect(screen.getByText('LOWER ESTIMATED ΔV')).toBeInTheDocument()
      expect(screen.getByText('FEWER SCREENED EVENTS')).toBeInTheDocument()
      expect(screen.getByText('LOWER RELATIVE RISK SCORE')).toBeInTheDocument()
    })

    it('triggers onRemoveCandidate when remove button is clicked', () => {
      const handleRemove = vi.fn()
      render(
        <CandidateComparison
          candidates={[mockCandidates[0], mockCandidates[1]]}
          onRemoveCandidate={handleRemove}
          onClear={vi.fn()}
        />
      )

      const removeBtn = screen.getByLabelText(/Remove candidate cand-001-alpha from comparison/i)
      fireEvent.click(removeBtn)
      expect(handleRemove).toHaveBeenCalledWith('cand-001-alpha')
    })

    it('triggers onClear when Clear All button is clicked', () => {
      const handleClear = vi.fn()
      render(
        <CandidateComparison
          candidates={[mockCandidates[0], mockCandidates[1]]}
          onRemoveCandidate={vi.fn()}
          onClear={handleClear}
        />
      )

      const clearBtn = screen.getByRole('button', { name: /clear all/i })
      fireEvent.click(clearBtn)
      expect(handleClear).toHaveBeenCalledTimes(1)
    })

    it('displays conservative disclaimer without claiming optimal or safe', () => {
      render(
        <CandidateComparison
          candidates={[mockCandidates[0], mockCandidates[1]]}
          onRemoveCandidate={vi.fn()}
          onClear={vi.fn()}
        />
      )

      expect(screen.getByText(/Does not constitute an operational flight approval/i)).toBeInTheDocument()
    })
  })

  describe('ResultsHeader DEMO MODE Provenance Banner', () => {
    it('renders DEMO MODE banner when demoMode is true', () => {
      render(
        <ResultsHeader
          runId="run-demo-001"
          planId="plan-demo-001"
          status="completed"
          demoMode={true}
          dataSource="demo"
          onBackToPlanner={vi.fn()}
        />
      )

      const banner = screen.getByTestId('demo-mode-provenance-banner')
      expect(banner).toBeInTheDocument()
      expect(screen.getAllByText(/DEMO MODE/i).length).toBeGreaterThanOrEqual(1)
      expect(within(banner).getByText(/Deterministic bundled reference run/i)).toBeInTheDocument()
      expect(within(banner).getByText(/TEME/i)).toBeInTheDocument()
      expect(within(banner).getByText(/UTC/i)).toBeInTheDocument()
    })

    it('does not render DEMO MODE banner when demoMode is false', () => {
      render(
        <ResultsHeader
          runId="run-live-001"
          planId="plan-live-001"
          status="completed"
          demoMode={false}
          dataSource="celestrak"
          onBackToPlanner={vi.fn()}
        />
      )

      expect(screen.queryByTestId('demo-mode-provenance-banner')).toBeNull()
    })
  })

  describe('GlobeLegend Multi-Candidate Comparison Palette', () => {
    it('renders multi-candidate comparison palette indicator', () => {
      render(<GlobeLegend />)
      expect(screen.getByText(/Multi-candidate comparison palette/i)).toBeInTheDocument()
    })
  })

  describe('MissionPresets Instant Demo Flow', () => {
    it('renders instant demo loading state when isDemoLoading is true', () => {
      render(
        <MissionPresets
          activePresetId="sso_demo"
          onSelectPreset={vi.fn()}
          onTryDemo={vi.fn()}
          isDemoLoading={true}
        />
      )

      expect(screen.getAllByText(/LOADING DEMO…/i).length).toBeGreaterThanOrEqual(1)
      expect(screen.getByTestId('open-guided-demo-btn')).toBeInTheDocument()
    })
  })

  describe('CandidateTradeoffExplorer Component', () => {
    it('renders header, explanatory copy, and non-operational indicators', () => {
      render(
        <CandidateTradeoffExplorer
          candidates={mockCandidates}
          onSelectCandidate={vi.fn()}
        />
      )

      expect(screen.getByText('CANDIDATE TRADE-OFF EXPLORER')).toBeInTheDocument()
      expect(screen.getByText(/Each point represents one candidate configuration from the evaluated search space/i)).toBeInTheDocument()
      expect(screen.getByText(/relative trade-offs between estimated propulsion demand and screening indicators/i)).toBeInTheDocument()
      expect(screen.getByText(/Screening heuristic • Backend-derived values • Non-operational/i)).toBeInTheDocument()
      expect(screen.getByTestId('plotly-tradeoff-scatter')).toBeInTheDocument()
    })

    it('initializes Plotly scatter plot with Delta-V on X and Risk Score on Y by default', () => {
      render(
        <CandidateTradeoffExplorer
          candidates={mockCandidates}
          onSelectCandidate={vi.fn()}
        />
      )

      expect(Plotly.react).toHaveBeenCalled()
      const calls = vi.mocked(Plotly.react).mock.calls
      const lastCall = calls[calls.length - 1]
      const traces = lastCall[1] as Array<Record<string, unknown>>
      const layout = lastCall[2] as Partial<Plotly.Layout>

      expect(traces[0].type).toBe('scatter')
      expect(traces[0].mode).toBe('markers')
      expect(traces[0].x).toEqual([32.5, 48.0, 75.2])
      expect(traces[0].y).toEqual([14.2, 28.5, 45.0])
      expect(layout.xaxis?.title).toEqual(expect.objectContaining({ text: 'Estimated Δv (m/s)' }))
      expect(layout.yaxis?.title).toEqual(expect.objectContaining({ text: 'Screening Risk Score (/100)' }))
    })

    it('formats hover tooltips with backend values and displays Not available for null fields', () => {
      render(
        <CandidateTradeoffExplorer
          candidates={mockCandidates}
          onSelectCandidate={vi.fn()}
        />
      )

      const calls = vi.mocked(Plotly.react).mock.calls
      const lastCall = calls[calls.length - 1]
      const traces = lastCall[1] as Array<{ text: string[] }>
      const tooltips = traces[0].text

      // cand-001 has null minimum_miss_distance_km
      expect(tooltips[0]).toContain('Candidate:</b> cand-001-alpha')
      expect(tooltips[0]).toContain('Rank:</b> #1')
      expect(tooltips[0]).toContain('Estimated Δv:</b> 32.50 m/s')
      expect(tooltips[0]).toContain('Screening Risk Score:</b> 14.2 / 100')
      expect(tooltips[0]).toContain('Minimum Miss Distance:</b> Not available')

      // cand-002 has 18.4 km minimum miss distance
      expect(tooltips[1]).toContain('Candidate:</b> cand-002-beta')
      expect(tooltips[1]).toContain('Minimum Miss Distance:</b> 18.40 km')
    })

    it('switches Y-axis metric to Event Count and Minimum Miss Distance', () => {
      render(
        <CandidateTradeoffExplorer
          candidates={mockCandidates}
          onSelectCandidate={vi.fn()}
        />
      )

      // Click Event Count
      const eventBtn = screen.getByTestId('tradeoff-metric-events')
      fireEvent.click(eventBtn)

      let calls = vi.mocked(Plotly.react).mock.calls
      let lastCall = calls[calls.length - 1]
      let traces = lastCall[1] as Array<Record<string, unknown>>
      let layout = lastCall[2] as Partial<Plotly.Layout>
      expect(traces[0].y).toEqual([0, 2, 5])
      expect(layout.yaxis?.title).toEqual(expect.objectContaining({ text: 'Screened Close-Approach Events (count)' }))

      // Click Minimum Miss Distance
      const missBtn = screen.getByTestId('tradeoff-metric-miss')
      fireEvent.click(missBtn)

      calls = vi.mocked(Plotly.react).mock.calls
      lastCall = calls[calls.length - 1]
      traces = lastCall[1] as Array<Record<string, unknown>>
      layout = lastCall[2] as Partial<Plotly.Layout>
      expect(traces[0].y).toEqual([null, 18.4, 8.2])
      expect(layout.yaxis?.title).toEqual(expect.objectContaining({ text: 'Minimum Miss Distance (km)' }))
    })

    it('highlights selected candidate and comparison candidates with distinct markers', () => {
      render(
        <CandidateTradeoffExplorer
          candidates={mockCandidates}
          selectedCandidateId="cand-001-alpha"
          comparisonCandidateIds={['cand-002-beta']}
          onSelectCandidate={vi.fn()}
        />
      )

      const calls = vi.mocked(Plotly.react).mock.calls
      const lastCall = calls[calls.length - 1]
      const traces = lastCall[1] as Array<{
        marker: { size: number[]; color: string[] }
      }>
      const marker = traces[0].marker

      // Selected candidate: larger size 14, color #00F0FF
      expect(marker.size[0]).toBe(14)
      expect(marker.color[0]).toBe('#00F0FF')

      // Comparison candidate: size 12
      expect(marker.size[1]).toBe(12)

      // Remaining candidate: size 8
      expect(marker.size[2]).toBe(8)
    })

    it('renders loading indicator when isLoading is true', () => {
      render(
        <CandidateTradeoffExplorer
          candidates={mockCandidates}
          isLoading={true}
          onSelectCandidate={vi.fn()}
        />
      )

      expect(screen.getByTestId('tradeoff-loading')).toBeInTheDocument()
      expect(screen.getByText('Loading candidate trade-off data…')).toBeInTheDocument()
    })
  })
})
