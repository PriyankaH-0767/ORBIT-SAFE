import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import * as Cesium from 'cesium'
import { OrbitGlobe } from '../components/results/OrbitGlobe'
import { getRunGlobe } from '../api/globe'
import { temeKmToCesiumFixed } from '../utils/cesiumFrames'
import type { GlobeResponse } from '../types/globe'

/**
 * Realistic Frozen P15 Backend Contract Fixture.
 * Sourced directly from docs/API.md and backend/app/schemas/globe.py.
 */
const FROZEN_P15_FIXTURE: GlobeResponse = {
  run_id: '481dc7f0-505f-4278-9b47-82e3fe6e18ff',
  status: 'completed',
  frame: 'TEME',
  time_scale: 'UTC',
  sample_step_seconds: 3600,
  epoch_start: '2026-10-02T12:00:00Z',
  epoch_end: '2026-10-05T12:00:00Z',
  candidate_count: 1,
  debris_count: 1,
  event_count: 1,
  candidates: [
    {
      candidate_id: 'a6fed8f9-f140-498f-8db3-ad94de861ff6',
      rank: 1,
      altitude_km: 550.0,
      inclination_deg: 97.5,
      raan_deg: 0.0,
      risk_score: 12.5,
      within_dv_budget: true,
      deployment_delay_minutes: 0.0,
      deployment_epoch: '2026-10-02T12:00:00Z',
      trajectory_start: '2026-10-02T12:00:00Z',
      trajectory_end: '2026-10-05T12:00:00Z',
      point_count: 2,
      trajectory: [
        {
          t: '2026-10-02T12:00:00Z',
          x_km: 6928.137,
          y_km: 0.0,
          z_km: 0.0,
          vx_km_s: 0.0,
          vy_km_s: 0.9928,
          vz_km_s: 7.5148,
        },
        {
          t: '2026-10-02T13:00:00Z',
          x_km: 6900.5,
          y_km: 120.0,
          z_km: 50.0,
          vx_km_s: 0.05,
          vy_km_s: 0.99,
          vz_km_s: 7.5,
        },
      ],
    },
  ],
  debris: [
    {
      norad_id: '700001',
      object_name: 'TEST DEBRIS',
      debris_db_id: 'deb-001',
      point_count: 2,
      trajectory: [
        {
          t: '2026-10-02T12:00:00Z',
          x_km: 6850.123,
          y_km: 120.456,
          z_km: -300.789,
          vx_km_s: 0.1234,
          vy_km_s: 7.45,
          vz_km_s: 0.05,
        },
        {
          t: '2026-10-02T13:00:00Z',
          x_km: 6840.0,
          y_km: 150.0,
          z_km: -280.0,
          vx_km_s: 0.12,
          vy_km_s: 7.44,
          vz_km_s: 0.05,
        },
      ],
    },
  ],
  events: [
    {
      event_id: 'bd96754c-789a-4123-bcde-0123456789ab',
      candidate_id: 'a6fed8f9-f140-498f-8db3-ad94de861ff6',
      debris_object_id: 'deb-001',
      debris_norad_id: '700001',
      tca: '2026-10-04T03:29:28.753588Z',
      miss_distance_km: 13.749,
      relative_velocity_km_s: 14.2,
      x_km: 269.236,
      y_km: 973.079,
      z_km: -6842.659,
    },
  ],
}

describe('P15 Frozen Globe API Contract Compliance', () => {
  const originalFetch = globalThis.fetch
  let capturedViewer: any = null

  beforeEach(() => {
    vi.clearAllMocks()
    capturedViewer = null
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    cleanup()
    globalThis.fetch = originalFetch
  })

  it('1. API client accepts and deserializes exact frozen P15 response schema', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(FROZEN_P15_FIXTURE), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    const response = await getRunGlobe('481dc7f0-505f-4278-9b47-82e3fe6e18ff')

    expect(response.run_id).toBe('481dc7f0-505f-4278-9b47-82e3fe6e18ff')
    expect(response.status).toBe('completed')
    expect(response.frame).toBe('TEME')
    expect(response.time_scale).toBe('UTC')
    expect(response.sample_step_seconds).toBe(3600)
    expect(response.epoch_start).toBe('2026-10-02T12:00:00Z')
    expect(response.epoch_end).toBe('2026-10-05T12:00:00Z')
    expect(response.candidates).toHaveLength(1)
    expect(response.debris).toHaveLength(1)
    expect(response.events).toHaveLength(1)

    // Verify candidate fields
    const cand = response.candidates[0]
    expect(cand.candidate_id).toBe('a6fed8f9-f140-498f-8db3-ad94de861ff6')
    expect(cand.trajectory_start).toBe('2026-10-02T12:00:00Z')
    expect(cand.trajectory_end).toBe('2026-10-05T12:00:00Z')
    expect(cand.trajectory).toHaveLength(2)
    expect(cand.trajectory[0].x_km).toBe(6928.137)

    // Verify debris fields
    const deb = response.debris[0]
    expect(deb.norad_id).toBe('700001')
    expect(deb.trajectory[0].x_km).toBe(6850.123)

    // Verify event fields
    const evt = response.events[0]
    expect(evt.event_id).toBe('bd96754c-789a-4123-bcde-0123456789ab')
    expect(evt.x_km).toBe(269.236)
    expect(evt.y_km).toBe(973.079)
    expect(evt.z_km).toBe(-6842.659)
  })

  it('2. OrbitGlobe renders candidate tracks, debris tracks, and event markers with clock initialization', () => {
    render(
      <OrbitGlobe
        globeData={FROZEN_P15_FIXTURE}
        showDebris={true}
        isPlaying={false}
        playbackSpeed={1}
        onViewerReady={(v) => {
          capturedViewer = v
        }}
      />
    )

    expect(capturedViewer).not.toBeNull()

    // Clock initialized strictly from epoch_start and epoch_end
    const expectedStartJulian = Cesium.JulianDate.fromIso8601('2026-10-02T12:00:00Z')
    const expectedStopJulian = Cesium.JulianDate.fromIso8601('2026-10-05T12:00:00Z')
    expect(capturedViewer.clock.startTime).toEqual(expectedStartJulian)
    expect(capturedViewer.clock.stopTime).toEqual(expectedStopJulian)
    expect(capturedViewer.clock.clockRange).toBe(Cesium.ClockRange.LOOP_STOP)

    // Check entity creation
    const addedEntities = capturedViewer.entities.add.mock.calls.map((c: any[]) => c[0].id)
    expect(addedEntities).toContain('candidate-orbit-a6fed8f9-f140-498f-8db3-ad94de861ff6')
    expect(addedEntities).toContain('candidate-marker-a6fed8f9-f140-498f-8db3-ad94de861ff6')
    expect(addedEntities).toContain('debris-orbit-700001')
    expect(addedEntities).toContain('debris-marker-700001')
    expect(addedEntities).toContain('event-marker-bd96754c-789a-4123-bcde-0123456789ab')

    // Find event marker entity call and verify coordinates stored
    const eventMarkerCall = capturedViewer.entities.add.mock.calls.find(
      (c: any[]) => c[0].id === 'event-marker-bd96754c-789a-4123-bcde-0123456789ab'
    )
    expect(eventMarkerCall).toBeDefined()
    expect(eventMarkerCall[0].properties.x_km).toBe(269.236)
    expect(eventMarkerCall[0].properties.y_km).toBe(973.079)
    expect(eventMarkerCall[0].properties.z_km).toBe(-6842.659)
    expect(eventMarkerCall[0].properties.tca).toBe('2026-10-04T03:29:28.753588Z')
  })

  it('3. OrbitGlobe throws explicit error if event marker is missing x_km, y_km, or z_km', () => {
    const invalidFixture: GlobeResponse = {
      ...FROZEN_P15_FIXTURE,
      events: [
        {
          event_id: 'bad-evt-001',
          tca: '2026-10-04T03:29:28.753588Z',
          miss_distance_km: 10.0,
          relative_velocity_km_s: 14.0,
          // Intentionally omitting x_km, y_km, z_km (or passing undefined)
          x_km: undefined as any,
          y_km: undefined as any,
          z_km: undefined as any,
        },
      ],
    }

    expect(() => {
      render(
        <OrbitGlobe
          globeData={invalidFixture}
          showDebris={true}
          isPlaying={false}
          playbackSpeed={1}
          onViewerReady={(v) => {
            capturedViewer = v
          }}
        />
      )
    }).toThrow(/missing required TEME coordinates/i)
  })

  it('4. temeKmToCesiumFixed throws error when coordinate is NaN or not a number', () => {
    expect(() => {
      temeKmToCesiumFixed(NaN, 100, 200, '2026-10-02T12:00:00Z')
    }).toThrow(/Invalid TEME coordinates/i)

    expect(() => {
      temeKmToCesiumFixed(100, undefined as any, 200, '2026-10-02T12:00:00Z')
    }).toThrow(/Invalid TEME coordinates/i)
  })
})
