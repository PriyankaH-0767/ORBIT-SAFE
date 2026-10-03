import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { OrbitGlobe } from '../components/results/OrbitGlobe'
import type { GlobeResponse } from '../types/globe'

const mockGlobeData: GlobeResponse = {
  run_id: 'run-p22-test',
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
      altitude_km: 550.0,
      inclination_deg: 97.5,
      raan_deg: 45.0,
      risk_score: 3.45,
      within_dv_budget: true,
      deployment_delay_minutes: 0.0,
      deployment_epoch: '2026-10-15T12:00:00Z',
      trajectory_start: '2026-10-15T12:00:00Z',
      trajectory_end: '2026-10-18T12:00:00Z',
      point_count: 2,
      trajectory: [
        { t: '2026-10-15T12:00:00Z', x_km: 6928.1, y_km: 0.0, z_km: 0.0, vx_km_s: 0.0, vy_km_s: 7.58, vz_km_s: 1.02 },
        { t: '2026-10-15T12:05:00Z', x_km: 6900.0, y_km: 100.0, z_km: 50.0, vx_km_s: 0.1, vy_km_s: 7.55, vz_km_s: 1.00 },
      ],
    },
  ],
  debris: [
    {
      norad_id: '25544',
      object_name: 'ISS (ZARYA)',
      debris_db_id: 'deb-001',
      point_count: 2,
      trajectory: [
        { t: '2026-10-15T12:00:00Z', x_km: 6780.0, y_km: 50.0, z_km: -20.0, vx_km_s: 0.0, vy_km_s: 7.6, vz_km_s: 0.5 },
        { t: '2026-10-15T12:05:00Z', x_km: 6770.0, y_km: 120.0, z_km: -10.0, vx_km_s: 0.0, vy_km_s: 7.59, vz_km_s: 0.51 },
      ],
    },
  ],
  events: [
    {
      event_id: 'evt-001',
      candidate_id: 'cand-001',
      debris_object_id: 'deb-001',
      debris_norad_id: '25544',
      tca: '2026-10-15T18:42:15Z',
      miss_distance_km: 4.12,
      relative_velocity_km_s: 14.85,
      x_km: 6850.2,
      y_km: 124.5,
      z_km: 890.1,
    },
  ],
}

describe('OrbitGlobe Component', () => {
  let capturedViewer: any = null

  beforeEach(() => {
    vi.clearAllMocks()
    capturedViewer = null
  })

  afterEach(() => {
    cleanup()
  })

  it('renders the globe mount container with accessible role and label', () => {
    render(
      <OrbitGlobe
        globeData={mockGlobeData}
        showDebris={true}
        isPlaying={false}
        playbackSpeed={1}
      />
    )

    const region = screen.getByRole('region', { name: /3d orbital visualization globe/i })
    expect(region).toBeInTheDocument()
  })

  it('adds entities for candidate orbit, debris track, and conjunction event marker', () => {
    render(
      <OrbitGlobe
        globeData={mockGlobeData}
        showDebris={true}
        isPlaying={false}
        playbackSpeed={1}
        onViewerReady={(v) => {
          capturedViewer = v
        }}
      />
    )

    expect(capturedViewer).not.toBeNull()
    expect(capturedViewer.entities.removeAll).toHaveBeenCalled()
    // 2 candidate entities (orbit + marker), 2 debris entities (orbit + marker), 1 event marker = 5 total
    expect(capturedViewer.entities.add).toHaveBeenCalledTimes(5)

    const addedCalls = capturedViewer.entities.add.mock.calls.map((call: any[]) => call[0].id)
    expect(addedCalls).toContain('candidate-orbit-cand-001')
    expect(addedCalls).toContain('candidate-marker-cand-001')
    expect(addedCalls).toContain('debris-orbit-25544')
    expect(addedCalls).toContain('debris-marker-25544')
    expect(addedCalls).toContain('event-marker-evt-001')
  })

  it('omits debris entities when showDebris is false', () => {
    render(
      <OrbitGlobe
        globeData={mockGlobeData}
        showDebris={false}
        isPlaying={false}
        playbackSpeed={1}
        onViewerReady={(v) => {
          capturedViewer = v
        }}
      />
    )

    const addedCalls = capturedViewer.entities.add.mock.calls.map((call: any[]) => call[0].id)
    expect(addedCalls).toContain('candidate-orbit-cand-001')
    expect(addedCalls).not.toContain('debris-orbit-25544')
    expect(addedCalls).not.toContain('debris-marker-25544')
    expect(addedCalls).toContain('event-marker-evt-001')
  })

  it('cleans up and destroys Cesium Viewer when component unmounts', () => {
    const { unmount } = render(
      <OrbitGlobe
        globeData={mockGlobeData}
        showDebris={true}
        isPlaying={false}
        playbackSpeed={1}
        onViewerReady={(v) => {
          capturedViewer = v
        }}
      />
    )

    unmount()
    expect(capturedViewer.destroy).toHaveBeenCalledTimes(1)
  })
})
