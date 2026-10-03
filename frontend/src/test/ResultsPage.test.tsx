import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { ResultsPage } from '../pages/ResultsPage'
import * as runsApi from '../api/runs'
import * as candidatesApi from '../api/candidates'
import * as eventsApi from '../api/events'
import * as heatmapApi from '../api/heatmap'
import * as globeApi from '../api/globe'
import * as validationApi from '../api/validation'
import { ApiError } from '../api/client'
import type { RunStatusResponse } from '../types/run'
import type { CandidateResultsResponse } from '../types/candidate'
import type { EventResultsResponse } from '../types/event'
import type { HeatmapResponse } from '../types/heatmap'
import type { GlobeResponse } from '../types/globe'
import type { ValidationResponse } from '../types/validation'

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
  run_id: 'test-run-101',
  plan_id: 'test-plan-202',
  status: 'completed',
  progress_percent: 100.0,
  current_stage: 'completed',
  message: 'Screening run complete',
  created_at: '2026-10-02T12:00:00Z',
  started_at: '2026-10-02T12:00:01Z',
  completed_at: '2026-10-02T12:00:05Z',
  error_message: null,
  candidate_count: 195,
  conjunction_event_count: 14,
  ranked_candidate_count: 195,
}

const mockCandidatesResponse: CandidateResultsResponse = {
  run_id: 'test-run-101',
  total: 45,
  limit: 20,
  offset: 0,
  candidates: [
    {
      candidate_id: 'cand-001',
      altitude_km: 500.0,
      inclination_deg: 97.4,
      raan_deg: 120.0,
      u0_deg: 45.0,
      deployment_delay_minutes: 10.0,
      deployment_epoch: '2026-10-04T12:10:00Z',
      delta_v_m_s: 35.5,
      propellant_mass_kg: 2.7,
      fuel_fraction: 0.027,
      within_dv_budget: true,
      risk_score: 8.5,
      accepted_event_count: 1,
      minimum_miss_distance_km: 12.34,
      uncertainty_level: 'nominal',
      rank: 1,
    },
    {
      candidate_id: 'cand-002',
      altitude_km: 510.0,
      inclination_deg: 97.5,
      raan_deg: 121.0,
      u0_deg: 46.0,
      deployment_delay_minutes: 20.0,
      deployment_epoch: '2026-10-04T12:20:00Z',
      delta_v_m_s: 48.0,
      propellant_mass_kg: 3.8,
      fuel_fraction: 0.038,
      within_dv_budget: true,
      risk_score: 16.2,
      accepted_event_count: 0,
      minimum_miss_distance_km: null,
      uncertainty_level: 'nominal',
      rank: 2,
    },
  ],
}

const mockEventsResponse: EventResultsResponse = {
  run_id: 'test-run-101',
  total: 35,
  limit: 20,
  offset: 0,
  events: [
    {
      id: 'evt-001',
      candidate_id: 'cand-099',
      debris_object_id: 'deb-123',
      debris_norad_id: '25544',
      debris_name: 'FENGYUN 1C DEB',
      tca: '2026-10-04T03:29:28.000Z',
      miss_distance_km: 2.15,
      relative_velocity_km_s: 14.12,
      threshold_km: 25.0,
      screening_source: 'sgp4_tle',
    },
  ],
}

const mockHeatmapResponse: HeatmapResponse = {
  run_id: 'test-run-101',
  status: 'completed',
  metric: 'risk_score',
  x_axis: 'delay_minutes',
  y_axis: 'altitude_km',
  inclination_values_deg: [97.4, 98.0],
  layers: [
    {
      inclination_deg: 97.4,
      altitude_values_km: [500.0, 510.0],
      delay_values_minutes: [10.0, 20.0],
      values: [
        [8.5, null],
        [null, 16.2],
      ],
      cells: [
        {
          candidate_id: 'cand-001',
          altitude_km: 500.0,
          inclination_deg: 97.4,
          delay_minutes: 10.0,
          risk_score: 8.5,
          rank: 1,
          delta_v_m_s: 35.5,
          within_dv_budget: true,
          accepted_event_count: 1,
          minimum_miss_distance_km: 12.34,
          uncertainty_level: 'nominal',
        },
      ],
    },
    {
      inclination_deg: 98.0,
      altitude_values_km: [500.0],
      delay_values_minutes: [10.0],
      values: [[25.0]],
      cells: [
        {
          candidate_id: 'cand-003',
          altitude_km: 500.0,
          inclination_deg: 98.0,
          delay_minutes: 10.0,
          risk_score: 25.0,
          rank: 3,
        },
      ],
    },
  ],
  total_candidates: 45,
  populated_cells: 2,
  min_risk_score: 8.5,
  max_risk_score: 25.0,
}

const mockGlobeResponse: GlobeResponse = {
  run_id: 'test-run-101',
  status: 'completed',
  frame: 'TEME',
  time_scale: 'UTC',
  sample_step_seconds: 300,
  epoch_start: '2026-10-15T12:00:00Z',
  epoch_end: '2026-10-18T12:00:00Z',
  candidate_count: 1,
  debris_count: 1,
  event_count: 1,
  candidates: [
    {
      candidate_id: 'cand-001',
      rank: 1,
      altitude_km: 500.0,
      inclination_deg: 97.4,
      raan_deg: 120.0,
      risk_score: 8.5,
      within_dv_budget: true,
      deployment_delay_minutes: 10.0,
      deployment_epoch: '2026-10-04T12:10:00Z',
      trajectory_start: '2026-10-04T12:10:00Z',
      trajectory_end: '2026-10-07T12:10:00Z',
      point_count: 2,
      trajectory: [
        { t: '2026-10-04T12:10:00Z', x_km: 6878.0, y_km: 0.0, z_km: 0.0, vx_km_s: 0.0, vy_km_s: 7.6, vz_km_s: 0.0 },
        { t: '2026-10-04T12:15:00Z', x_km: 6860.0, y_km: 100.0, z_km: 20.0, vx_km_s: 0.1, vy_km_s: 7.58, vz_km_s: 0.02 },
      ],
    },
  ],
  debris: [
    {
      norad_id: '25544',
      object_name: 'DEBRIS-01',
      point_count: 2,
      trajectory: [
        { t: '2026-10-04T12:10:00Z', x_km: 6780.0, y_km: 0.0, z_km: 0.0, vx_km_s: 0.0, vy_km_s: 7.65, vz_km_s: 0.0 },
        { t: '2026-10-04T12:15:00Z', x_km: 6770.0, y_km: 50.0, z_km: 10.0, vx_km_s: 0.05, vy_km_s: 7.64, vz_km_s: 0.01 },
      ],
    },
  ],
  events: [
    {
      event_id: 'evt-001',
      candidate_id: 'cand-001',
      debris_object_id: 'deb-001',
      debris_norad_id: '25544',
      tca: '2026-10-04T18:22:15Z',
      miss_distance_km: 12.34,
      relative_velocity_km_s: 14.85,
      x_km: 6850.0,
      y_km: 100.0,
      z_km: 500.0,
    },
  ],
}

const mockValidationResponse: ValidationResponse = {
  validation_id: 'val-test-123',
  run_id: 'test-run-101',
  status: 'completed',
  source: 'socrates_demo_fixture',
  source_fetched_at: '2026-10-15T12:00:00Z',
  validation_created_at: '2026-10-15T12:05:00Z',
  summary: {
    d_dato_event_count: 8,
    external_event_count: 10,
    matched_event_count: 7,
    d_dato_only_count: 1,
    external_only_count: 3,
    external_coverage_percent: 70.0,
    d_dato_match_rate_percent: 87.5,
    mean_abs_tca_error_seconds: 14.2,
    max_abs_tca_error_seconds: 28.5,
    mean_abs_miss_distance_difference_km: 0.125,
    max_abs_miss_distance_difference_km: 0.45,
  },
  matches: [
    {
      d_dato_event_id: 'evt-001',
      external_event_id: 'SOC-DEMO-001',
      candidate_id: 'cand-001',
      debris_norad_id: '25544',
      tca_d_dato: '2026-10-04T03:29:28.000Z',
      tca_external: '2026-10-04T03:29:30.000Z',
      tca_error_seconds: -2.0,
      miss_distance_d_dato_km: 2.15,
      miss_distance_external_km: 2.2,
      miss_distance_difference_km: -0.05,
      match_criteria: ['norad_id', 'tca_tolerance'],
    },
  ],
  d_dato_only: [
    {
      d_dato_event_id: 'evt-002',
      candidate_id: 'cand-002',
      debris_norad_id: '33333',
      tca: '2026-10-04T05:00:00Z',
      miss_distance_km: 15.0,
      relative_velocity_km_s: 12.0,
      notes: 'No matching external reference event within configured tolerances.',
    },
  ],
  external_only: [
    {
      external_event_id: 'SOC-DEMO-099',
      candidate_identifier: 'EXT-SAT-1',
      debris_norad_id: '99999',
      tca: '2026-10-04T06:00:00Z',
      miss_distance_km: 1.5,
      relative_velocity_km_s: 14.0,
      notes: 'Unmatched in evaluated candidate screening envelope.',
    },
  ],
  notes: [
    'NON-OPERATIONAL VALIDATION: External reference evidence only.',
    'Reference source: SOCRATES demo fixture dataset.',
  ],
}

describe('ResultsPage Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(runsApi, 'getRun').mockResolvedValue(mockRunResponse)
    vi.spyOn(candidatesApi, 'getRunCandidates').mockResolvedValue(mockCandidatesResponse)
    vi.spyOn(eventsApi, 'getRunEvents').mockResolvedValue(mockEventsResponse)
    vi.spyOn(heatmapApi, 'getRunHeatmap').mockResolvedValue(mockHeatmapResponse)
    vi.spyOn(globeApi, 'getRunGlobe').mockResolvedValue(mockGlobeResponse)
    vi.spyOn(validationApi, 'getRunValidation').mockRejectedValue(new ApiError('Validation not found', 404))
    vi.spyOn(validationApi, 'createValidation').mockResolvedValue(mockValidationResponse)
  })

  it('1. loads and displays authoritative run summary metrics directly from GET /runs/{run_id}', async () => {
    render(<ResultsPage runId="test-run-101" />)

    // Verify loading of header & non-operational disclaimer
    expect(screen.getByText('D-DATO Screening Results')).toBeInTheDocument()
    expect(
      screen.getByText(/Early-stage screening results. Not an operational collision assessment./i)
    ).toBeInTheDocument()

    // Verify summary metrics populated from run status (195 evaluated, 195 ranked, 14 events)
    await waitFor(() => {
      expect(screen.getByText('Candidates Screened')).toBeInTheDocument()
      expect(screen.getByText('Candidates Ranked')).toBeInTheDocument()
      expect(screen.getByText('Close Approaches')).toBeInTheDocument()
    })

    // Numbers from mockRunResponse
    expect(screen.getAllByText('195')).toHaveLength(2)
    expect(screen.getByText('14')).toBeInTheDocument()

    expect(runsApi.getRun).toHaveBeenCalledWith('test-run-101')
  })

  it('2. renders candidate table with backend fields, formatted units, and null miss distance', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('cand-001')).toBeInTheDocument()
      expect(screen.getByText('cand-002')).toBeInTheDocument()
    })

    expect(screen.getByText('Rank 1')).toBeInTheDocument()
    expect(screen.getByText('Rank 2')).toBeInTheDocument()
    expect(screen.getByText('500.0')).toBeInTheDocument()
    expect(screen.getByText('12.34')).toBeInTheDocument()

    // cand-002 null miss distance shows '—'
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThan(0)
  })

  it('3. candidate pagination fetches requested offset without recomputing rankings', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('cand-001')).toBeInTheDocument()
    })

    // Look for candidates pagination next button
    const nextButtons = screen.getAllByRole('button', { name: /Next →/i })
    expect(nextButtons.length).toBeGreaterThanOrEqual(1)

    // Click candidates Next button
    fireEvent.click(nextButtons[0])

    await waitFor(() => {
      expect(candidatesApi.getRunCandidates).toHaveBeenCalledWith('test-run-101', 20, 20)
    })
  })

  it('4. event table renders backend event fields and pagination fetches next page', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('25544')).toBeInTheDocument()
      expect(screen.getByText('2026-10-04 03:29:28 UTC')).toBeInTheDocument()
    })

    const nextButtons = screen.getAllByRole('button', { name: /Next →/i })
    if (nextButtons.length > 1) {
      fireEvent.click(nextButtons[1])
      await waitFor(() => {
        expect(eventsApi.getRunEvents).toHaveBeenCalledWith('test-run-101', 20, 20)
      })
    }
  })

  it('5. candidate selection opens detail panel with no frontend science recomputation', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('cand-001')).toBeInTheDocument()
    })

    // Click candidate row
    fireEvent.click(screen.getByText('cand-001'))

    // Detail panel displays
    await waitFor(() => {
      expect(screen.getByTestId('candidate-detail-panel')).toBeInTheDocument()
      expect(screen.getByText('Candidate: cand-001')).toBeInTheDocument()
      expect(screen.getByText('35.50 m/s')).toBeInTheDocument()
      expect(screen.getByText('2.70%')).toBeInTheDocument()
    })

    // Close panel
    const closeBtn = screen.getByRole('button', { name: /Close detail panel/i })
    fireEvent.click(closeBtn)

    expect(screen.queryByTestId('candidate-detail-panel')).not.toBeInTheDocument()
  })

  it('6. empty candidate and event states display neutral informational text', async () => {
    vi.spyOn(candidatesApi, 'getRunCandidates').mockResolvedValueOnce({
      run_id: 'test-run-101',
      total: 0,
      limit: 20,
      offset: 0,
      candidates: [],
    })

    vi.spyOn(eventsApi, 'getRunEvents').mockResolvedValueOnce({
      run_id: 'test-run-101',
      total: 0,
      limit: 20,
      offset: 0,
      events: [],
    })

    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('No candidate results are available yet.')).toBeInTheDocument()
      expect(screen.getByText('No close-approach events were detected for this run.')).toBeInTheDocument()
    })
  })

  it('7. displays user-friendly error message on 404 run not found', async () => {
    vi.spyOn(runsApi, 'getRun').mockRejectedValueOnce(
      new ApiError('Not found', 404)
    )

    render(<ResultsPage runId="invalid-run-999" />)

    await waitFor(() => {
      expect(screen.getByText('Screening Run Unavailable')).toBeInTheDocument()
      expect(
        screen.getByText(/Screening run 'invalid-run-999' not found/i)
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Return to Planner/i })).toBeInTheDocument()
    })
  })

  it('8. displays user-friendly error message on network failure', async () => {
    vi.spyOn(runsApi, 'getRun').mockRejectedValueOnce(
      new ApiError('Failed to fetch', 0)
    )

    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('Screening Run Unavailable')).toBeInTheDocument()
      expect(screen.getByText(/Unable to connect to D-DATO backend/i)).toBeInTheDocument()
    })
  })

  it('9. renders Risk Heatmap section with backend-provided inclination slices and summary metrics', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('Screening Risk Heatmap')).toBeInTheDocument()
      expect(screen.getByTestId('heatmap-controls')).toBeInTheDocument()
      expect(screen.getByTestId('heatmap-chart-container')).toBeInTheDocument()
    })

    // Inclination slices present in selector
    expect(screen.getAllByText('97.4°').length).toBeGreaterThan(0)
    expect(screen.getAllByText('98.0°').length).toBeGreaterThan(0)

    // Summary metrics in controls
    const controls = screen.getByTestId('heatmap-controls')
    expect(within(controls).getByText('Min Risk (Run)')).toBeInTheDocument()
    expect(within(controls).getByText('8.5')).toBeInTheDocument()
    expect(within(controls).getByText('Max Risk (Run)')).toBeInTheDocument()
    expect(within(controls).getByText('25.0')).toBeInTheDocument()
  })

  it('10. allows switching inclination slice in heatmap controls', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /Inclination Slice/i })).toBeInTheDocument()
    })

    const select = screen.getByRole('combobox', { name: /Inclination Slice/i })
    fireEvent.change(select, { target: { value: '98' } })

    await waitFor(() => {
      expect(screen.getByText('98.0° slice')).toBeInTheDocument()
    })
  })

  it('11. displays empty state when heatmap layers are empty', async () => {
    vi.spyOn(heatmapApi, 'getRunHeatmap').mockResolvedValueOnce({
      run_id: 'test-run-101',
      status: 'completed',
      metric: 'risk_score',
      x_axis: 'delay_minutes',
      y_axis: 'altitude_km',
      inclination_values_deg: [],
      layers: [],
      total_candidates: 0,
      populated_cells: 0,
    })

    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('No Heatmap Data')).toBeInTheDocument()
      expect(screen.getByText('No heatmap data is available for this run yet.')).toBeInTheDocument()
    })
  })

  it('12. displays error state and retry button when heatmap fails to load', async () => {
    vi.spyOn(heatmapApi, 'getRunHeatmap').mockRejectedValueOnce(
      new ApiError('Failed to load heatmap data', 500)
    )

    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('Failed to load heatmap data')).toBeInTheDocument()
    })

    const retryButtons = screen.getAllByRole('button', { name: /Retry/i })
    expect(retryButtons.length).toBeGreaterThan(0)
  })

  it('13. renders the 3D orbital trajectory & conjunction globe section with TEME frame badge and legend', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('3D Orbital Trajectory & Conjunction Globe')).toBeInTheDocument()
      expect(screen.getByText(/TEME frame • 1 cand • 1 debris/i)).toBeInTheDocument()
      expect(screen.getByText('Trajectory & Marker Classification')).toBeInTheDocument()
      expect(screen.getByText(/Coordinate data:/i)).toBeInTheDocument()
      expect(screen.getByText(/Display transform:/i)).toBeInTheDocument()
      expect(screen.getAllByRole('button', { name: /Reset View/i }).length).toBeGreaterThan(0)
    })
  })

  it('14. handles globe error state and retry action', async () => {
    vi.spyOn(globeApi, 'getRunGlobe').mockRejectedValueOnce(
      new ApiError('Unable to load 3D globe data.', 500)
    )

    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('Unable to load 3D globe data.')).toBeInTheDocument()
    })

    const retryButtons = screen.getAllByRole('button', { name: /Retry/i })
    expect(retryButtons.length).toBeGreaterThan(0)
  })

  it('15. handles globe empty state when no candidate or debris tracks exist', async () => {
    vi.spyOn(globeApi, 'getRunGlobe').mockResolvedValueOnce({
      run_id: 'test-run-101',
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

    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('No Orbital Data')).toBeInTheDocument()
      expect(screen.getByText('No orbital visualization data is available for this run.')).toBeInTheDocument()
    })
  })

  it('16. renders validation section in unvalidated state when GET /validation returns 404 VALIDATION_NOT_FOUND', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('External Reference Validation')).toBeInTheDocument()
      expect(screen.getByText('No External Validation Executed Yet')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Run External Validation/i })).toBeInTheDocument()
    })
  })

  it('17. runs external validation on button click, triggers POST, displays loading state, and populates results', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Run External Validation/i })).toBeInTheDocument()
    })

    const runBtn = screen.getByRole('button', { name: /Run External Validation/i })
    fireEvent.click(runBtn)

    await waitFor(() => {
      expect(validationApi.createValidation).toHaveBeenCalledWith('test-run-101', {
        source: 'socrates',
        tca_tolerance_seconds: 300,
        miss_distance_tolerance_km: 5,
        demo_mode: true,
      })
      expect(screen.getByText('Synthetic demo reference data')).toBeInTheDocument()
      expect(screen.getByText('Matched Events (1)')).toBeInTheDocument()
      expect(screen.getByText('70.0%')).toBeInTheDocument()
    })
  })

  it('18. renders persisted validation results when GET /validation returns 200 on initial load', async () => {
    vi.spyOn(validationApi, 'getRunValidation').mockResolvedValueOnce(mockValidationResponse)

    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('Synthetic demo reference data')).toBeInTheDocument()
      expect(screen.getByText('Matched Conjunction Events (1)')).toBeInTheDocument()
      expect(screen.getByText('SOC-DEMO-001')).toBeInTheDocument()
      expect(screen.getByText('D-DATO-only (1)')).toBeInTheDocument()
      expect(screen.getByText('External-only (1)')).toBeInTheDocument()
      expect(screen.getByText(/NON-OPERATIONAL VALIDATION: External reference evidence only/i)).toBeInTheDocument()
    })
  })

  it('19. handles 503 VALIDATION_SOURCE_UNAVAILABLE with clear provenance message and retry option', async () => {
    vi.spyOn(validationApi, 'createValidation').mockRejectedValueOnce(
      new ApiError('Source unavailable', 503)
    )

    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Run External Validation/i })).toBeInTheDocument()
    })

    const runBtn = screen.getByRole('button', { name: /Run External Validation/i })
    fireEvent.click(runBtn)

    await waitFor(() => {
      expect(
        screen.getByText(/the external reference source is currently unavailable/i)
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument()
    })
  })

  it('20. cross-links candidate selection from validation matched table into CandidateDetailPanel', async () => {
    vi.spyOn(validationApi, 'getRunValidation').mockResolvedValueOnce(mockValidationResponse)

    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /cand-001/i })).toBeInTheDocument()
    })

    // Click candidate link in validation matched table
    const candBtn = screen.getByRole('button', { name: /cand-001/i })
    fireEvent.click(candBtn)

    // Verify CandidateDetailPanel opened for cand-001
    await waitFor(() => {
      expect(screen.getByTestId('candidate-detail-panel')).toBeInTheDocument()
      expect(screen.getByText(/Candidate:\s*cand-001/i)).toBeInTheDocument()
    })
  })

  it('21. renders export controls section with CSV and PDF download buttons in ResultsPage', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      expect(screen.getByText('Export Results')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Download CSV Package/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Download PDF Report/i })).toBeInTheDocument()
    })
  })

  it('22. integrates all 7 visual sections: Summary, Candidates, Events, Heatmap, Globe, Validation, and Exports', async () => {
    render(<ResultsPage runId="test-run-101" />)

    await waitFor(() => {
      // 1. Run Summary
      expect(screen.getByText('Candidates Screened')).toBeInTheDocument()
      // 2. Candidate Results
      expect(screen.getByText('Ranked Deployment Candidates')).toBeInTheDocument()
      // 3. Conjunction Events
      expect(screen.getByText('Close-Approach Conjunction Events')).toBeInTheDocument()
      // 4. Risk Heatmap
      expect(screen.getByText('Screening Risk Heatmap')).toBeInTheDocument()
      // 5. 3D Globe
      expect(screen.getByText('3D Orbital Trajectory & Conjunction Globe')).toBeInTheDocument()
      // 6. External Validation
      expect(screen.getByText('External Reference Validation')).toBeInTheDocument()
      // 7. Exports
      expect(screen.getByText('Export Results')).toBeInTheDocument()
    })
  })
})


