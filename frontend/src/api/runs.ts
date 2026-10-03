import { request } from './client'
import type { RunStatusResponse } from '../types/run'

/**
 * Poll execution lifecycle status and progress for a screening run (GET /api/v1/runs/{run_id})
 */
export async function getRun(runId: string): Promise<RunStatusResponse> {
  return request<RunStatusResponse>(`/api/v1/runs/${encodeURIComponent(runId)}`, {
    method: 'GET',
  })
}
