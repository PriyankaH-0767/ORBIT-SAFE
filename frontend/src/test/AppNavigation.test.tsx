import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { App } from '../App'
import * as runsApi from '../api/runs'
import * as candidatesApi from '../api/candidates'
import * as eventsApi from '../api/events'
import * as heatmapApi from '../api/heatmap'
import * as globeApi from '../api/globe'
import type { RunStatusResponse } from '../types/run'
import { navigateTo } from '../utils/router'

vi.mock('plotly.js-dist-min', () => ({
  default: {
    react: vi.fn().mockImplementation(() => Promise.resolve()),
    purge: vi.fn(),
    Plots: {
      resize: vi.fn(),
    },
  },
}))

const mockRunResponse: RunStatusResponse = {
  run_id: 'run-direct-456',
  plan_id: 'plan-789',
  status: 'completed',
  progress_percent: 100.0,
  current_stage: 'completed',
  message: 'Screening run complete',
  created_at: '2026-10-02T12:00:00Z',
  started_at: '2026-10-02T12:00:01Z',
  completed_at: '2026-10-02T12:00:05Z',
  error_message: null,
  candidate_count: 50,
  conjunction_event_count: 5,
  ranked_candidate_count: 50,
}

describe('App Navigation and Route State', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(runsApi, 'getRun').mockResolvedValue(mockRunResponse)
    vi.spyOn(candidatesApi, 'getRunCandidates').mockResolvedValue({
      run_id: 'run-direct-456',
      total: 1,
      limit: 20,
      offset: 0,
      candidates: [
        {
          candidate_id: 'cand-nav-1',
          altitude_km: 500.0,
          inclination_deg: 97.4,
          raan_deg: 120.0,
          u0_deg: 45.0,
          deployment_delay_minutes: 10.0,
          delta_v_m_s: 35.5,
          propellant_mass_kg: 2.7,
          fuel_fraction: 0.027,
          within_dv_budget: true,
          risk_score: 8.5,
          rank: 1,
        },
      ],
    })
    vi.spyOn(eventsApi, 'getRunEvents').mockResolvedValue({
      run_id: 'run-direct-456',
      total: 0,
      limit: 20,
      offset: 0,
      events: [],
    })
    vi.spyOn(heatmapApi, 'getRunHeatmap').mockResolvedValue({
      run_id: 'run-direct-456',
      status: 'completed',
      metric: 'risk_score',
      x_axis: 'delay_minutes',
      y_axis: 'altitude_km',
      inclination_values_deg: [97.4],
      layers: [],
      total_candidates: 1,
      populated_cells: 1,
    })
    vi.spyOn(globeApi, 'getRunGlobe').mockResolvedValue({
      run_id: 'run-direct-456',
      status: 'completed',
      frame: 'TEME',
      time_scale: 'UTC',
      sample_step_seconds: 300,
      epoch_start: '2026-10-15T12:00:00Z',
      epoch_end: '2026-10-18T12:00:00Z',
      candidate_count: 0,
      debris_count: 0,
      event_count: 0,
      candidates: [],
      debris: [],
      events: [],
    })
  })

  it('renders PlannerPage when route is /', () => {
    navigateTo('/')
    render(<App />)

    expect(screen.getByText(/Mission Planning & Screening Envelope/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Launch Screening Run/i })).toBeInTheDocument()
  })

  it('directly renders ResultsPage when navigated to /results/:runId', async () => {
    navigateTo('/results/run-direct-456')
    render(<App />)

    expect(screen.getByText('D-DATO Screening Results')).toBeInTheDocument()
    expect(screen.getByText('run-direct-456')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('cand-nav-1')).toBeInTheDocument()
      expect(screen.getByText('Rank 1')).toBeInTheDocument()
      expect(screen.getAllByText('50')).toHaveLength(2)
    })
  })
})
