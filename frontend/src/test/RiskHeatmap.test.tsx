import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { RiskHeatmap } from '../components/results/RiskHeatmap'
import { buildHeatmapTrace } from '../utils/heatmap'
import type { HeatmapLayer } from '../types/heatmap'
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

const mockLayer: HeatmapLayer = {
  inclination_deg: 97.5,
  altitude_values_km: [500.0, 550.0],
  delay_values_minutes: [0.0, 30.0],
  values: [
    [12.4, null],
    [18.9, 32.1],
  ],
  cells: [
    {
      candidate_id: 'cand-001',
      altitude_km: 500.0,
      inclination_deg: 97.5,
      delay_minutes: 0.0,
      risk_score: 12.4,
      rank: 1,
      delta_v_m_s: 45.2,
      within_dv_budget: true,
      accepted_event_count: 2,
      minimum_miss_distance_km: 7.82,
      uncertainty_level: 'nominal',
    },
    {
      candidate_id: 'cand-002',
      altitude_km: 550.0,
      inclination_deg: 97.5,
      delay_minutes: 0.0,
      risk_score: 18.9,
      rank: 2,
      delta_v_m_s: 60.1,
      within_dv_budget: true,
      accepted_event_count: 0,
      minimum_miss_distance_km: null,
      uncertainty_level: 'nominal',
    },
    {
      candidate_id: 'cand-003',
      altitude_km: 550.0,
      inclination_deg: 97.5,
      delay_minutes: 30.0,
      risk_score: 32.1,
      rank: 3,
      delta_v_m_s: 75.0,
      within_dv_budget: false,
      accepted_event_count: 5,
      minimum_miss_distance_km: 1.45,
      uncertainty_level: 'low',
    },
  ],
}

describe('RiskHeatmap Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    cleanup()
  })

  it('buildHeatmapTrace correctly structures matrix orientation and hover data', () => {
    const { hoverText, customData } = buildHeatmapTrace(mockLayer)

    // Row 0, Col 0: cand-001 (500 km, 0 min, populated)
    expect(customData[0][0]?.candidate_id).toBe('cand-001')
    expect(hoverText[0][0]).toContain('Candidate:</b> cand-001')
    expect(hoverText[0][0]).toContain('Rank:</b> Rank 1')
    expect(hoverText[0][0]).toContain('Risk Score:</b> 12.4')
    expect(hoverText[0][0]).toContain('Altitude:</b> 500.0 km')
    expect(hoverText[0][0]).toContain('Delay:</b> 0.0 min')

    // Row 0, Col 1: null cell (500 km, 30 min, null)
    expect(customData[0][1]).toBeNull()
    expect(hoverText[0][1]).toContain('No persisted candidate at this grid location.')
    expect(hoverText[0][1]).toContain('Altitude:</b> 500.0 km')
    expect(hoverText[0][1]).toContain('Delay:</b> 30.0 min')

    // Row 1, Col 1: cand-003 (550 km, 30 min, populated)
    expect(customData[1][1]?.candidate_id).toBe('cand-003')
    expect(hoverText[1][1]).toContain('Candidate:</b> cand-003')
    expect(hoverText[1][1]).toContain('Risk Score:</b> 32.1')
  })

  it('renders loading state when isLoading is true', () => {
    render(<RiskHeatmap layer={null} isLoading={true} />)

    expect(screen.getByText('Loading screening risk heatmap…')).toBeInTheDocument()
    expect(screen.getByTestId('heatmap-loading')).toBeInTheDocument()
  })

  it('initializes Plotly chart with Viridis scale, zmin 0, zmax 100, and connectgaps false', () => {
    render(<RiskHeatmap layer={mockLayer} isLoading={false} />)

    expect(screen.getByTestId('heatmap-chart-container')).toBeInTheDocument()
    expect(Plotly.react).toHaveBeenCalledTimes(1)

    const callArgs = vi.mocked(Plotly.react).mock.calls[0]
    const traces = callArgs[1] as Array<Record<string, unknown>>
    const layout = callArgs[2] as Partial<Plotly.Layout>

    expect(traces[0].type).toBe('heatmap')
    expect(traces[0].colorscale).toBe('Viridis')
    expect(traces[0].zmin).toBe(0)
    expect(traces[0].zmax).toBe(100)
    expect(traces[0].connectgaps).toBe(false)
    expect(traces[0].x).toEqual([0.0, 30.0])
    expect(traces[0].y).toEqual([500.0, 550.0])

    expect(layout.title?.text).toContain('Screening Risk Heatmap — 97.5°')
  })

  it('cleans up Plotly instance with purge on unmount', () => {
    const { unmount } = render(<RiskHeatmap layer={mockLayer} isLoading={false} />)
    unmount()

    expect(Plotly.purge).toHaveBeenCalledTimes(1)
  })
})
