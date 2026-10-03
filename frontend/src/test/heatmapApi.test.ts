import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getRunHeatmap } from '../api/heatmap'
import * as client from '../api/client'
import type { HeatmapResponse } from '../types/heatmap'

describe('Heatmap API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('forms correct URL without inclination parameter', async () => {
    const mockResponse: HeatmapResponse = {
      run_id: 'run-123',
      status: 'completed',
      metric: 'risk_score',
      x_axis: 'delay_minutes',
      y_axis: 'altitude_km',
      inclination_values_deg: [97.5],
      layers: [],
      total_candidates: 10,
      populated_cells: 5,
      min_risk_score: 1.2,
      max_risk_score: 15.4,
    }

    const requestSpy = vi.spyOn(client, 'request').mockResolvedValue(mockResponse)

    const result = await getRunHeatmap('run-123')

    expect(requestSpy).toHaveBeenCalledWith(
      '/api/v1/runs/run-123/heatmap',
      { method: 'GET' }
    )
    expect(result).toEqual(mockResponse)
  })

  it('forms correct URL with inclination_deg query parameter', async () => {
    const mockResponse: HeatmapResponse = {
      run_id: 'run-456',
      status: 'completed',
      metric: 'risk_score',
      x_axis: 'delay_minutes',
      y_axis: 'altitude_km',
      inclination_values_deg: [97.0, 97.5, 98.0],
      layers: [],
      total_candidates: 30,
      populated_cells: 18,
      min_risk_score: 2.1,
      max_risk_score: 24.5,
    }

    const requestSpy = vi.spyOn(client, 'request').mockResolvedValue(mockResponse)

    const result = await getRunHeatmap('run-456', 97.5)

    expect(requestSpy).toHaveBeenCalledWith(
      '/api/v1/runs/run-456/heatmap?inclination_deg=97.5',
      { method: 'GET' }
    )
    expect(result).toEqual(mockResponse)
  })
})
