import { describe, it, expect } from 'vitest'
import * as Cesium from 'cesium'
import { temeKmToCesiumFixed } from '../utils/cesiumFrames'

describe('temeKmToCesiumFixed transformation helper', () => {
  it('converts kilometer positions to meters before multiplying by pseudo-fixed rotation matrix', () => {
    // 6800 km altitude along TEME X
    const x_km = 6800.0
    const y_km = 1200.0
    const z_km = -3400.0
    const isoTime = '2026-10-15T12:00:00Z'

    const result = temeKmToCesiumFixed(x_km, y_km, z_km, isoTime)

    // Result should be a valid Cartesian3 with magnitude in meters (~7696 km = ~7.696e6 m)
    const expectedMagnitudeMeters = Math.hypot(x_km * 1000, y_km * 1000, z_km * 1000)
    const actualMagnitude = Cesium.Cartesian3.magnitude(result)

    // Rotation preserves vector length / magnitude
    expect(actualMagnitude).toBeCloseTo(expectedMagnitudeMeters, 1)
  })

  it('accepts both ISO 8601 string and Cesium.JulianDate timestamps identically', () => {
    const isoTime = '2026-10-15T18:30:00Z'
    const julianDate = Cesium.JulianDate.fromIso8601(isoTime)

    const resFromIso = temeKmToCesiumFixed(7000.0, 0.0, 0.0, isoTime)
    const resFromJulian = temeKmToCesiumFixed(7000.0, 0.0, 0.0, julianDate)

    expect(resFromIso.x).toBeCloseTo(resFromJulian.x, 3)
    expect(resFromIso.y).toBeCloseTo(resFromJulian.y, 3)
    expect(resFromIso.z).toBeCloseTo(resFromJulian.z, 3)
  })

  it('computes time-dependent Earth rotation (different positions at different times for same TEME vector)', () => {
    const t0 = '2026-10-15T12:00:00Z'
    const t1 = '2026-10-15T18:00:00Z' // 6 hours later (~90 degrees of Earth rotation)

    const pos0 = temeKmToCesiumFixed(7000.0, 0.0, 0.0, t0)
    const pos1 = temeKmToCesiumFixed(7000.0, 0.0, 0.0, t1)

    // Magnitudes must be identical (7000 km in meters = 7,000,000 m)
    expect(Cesium.Cartesian3.magnitude(pos0)).toBeCloseTo(7000000.0, 1)
    expect(Cesium.Cartesian3.magnitude(pos1)).toBeCloseTo(7000000.0, 1)

    // Due to 6h Earth rotation in pseudo-fixed frame, the X/Y components differ
    expect(pos0.x).not.toBeCloseTo(pos1.x, 1)
  })

  it('transforms event marker coordinates at exact backend TCA without interpolation', () => {
    const eventMarker = {
      event_id: 'evt-001',
      candidate_id: 'cand-001',
      debris_norad_id: '25544',
      tca: '2026-10-16T04:22:15Z',
      x_km: 6850.2,
      y_km: 124.5,
      z_km: 890.1,
      miss_distance_km: 4.12,
    }

    const transformed = temeKmToCesiumFixed(
      eventMarker.x_km,
      eventMarker.y_km,
      eventMarker.z_km,
      eventMarker.tca
    )

    const rawMagnitudeMeters = Math.hypot(
      eventMarker.x_km * 1000,
      eventMarker.y_km * 1000,
      eventMarker.z_km * 1000
    )
    expect(Cesium.Cartesian3.magnitude(transformed)).toBeCloseTo(rawMagnitudeMeters, 1)
  })
})
