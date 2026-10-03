import { request } from './client'
import type { EventResultsResponse } from '../types/event'

/**
 * Retrieve close-approach conjunction events detected during a screening run.
 * (GET /api/v1/runs/{run_id}/events)
 */
export async function getRunEvents(
  runId: string,
  limit = 20,
  offset = 0
): Promise<EventResultsResponse> {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  return request<EventResultsResponse>(
    `/api/v1/runs/${encodeURIComponent(runId)}/events?${query.toString()}`,
    {
      method: 'GET',
    }
  )
}
