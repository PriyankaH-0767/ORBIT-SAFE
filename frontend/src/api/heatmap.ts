import { request } from './client'
import type { HeatmapResponse } from '../types/heatmap'

/**
 * Retrieve 2D risk heatmap matrix data for a screening run.
 * (GET /api/v1/runs/{run_id}/heatmap)
 *
 * @param runId Unique screening run identifier
 * @param inclinationDeg Optional inclination slice filter in degrees
 */
export async function getRunHeatmap(
  runId: string,
  inclinationDeg?: number
): Promise<HeatmapResponse> {
  const query = new URLSearchParams()
  if (inclinationDeg != null) {
    query.set('inclination_deg', String(inclinationDeg))
  }
  const queryString = query.toString() ? `?${query.toString()}` : ''
  return request<HeatmapResponse>(
    `/api/v1/runs/${encodeURIComponent(runId)}/heatmap${queryString}`,
    {
      method: 'GET',
    }
  )
}
