import { request } from './client'
import type { CandidateResultsResponse } from '../types/candidate'

/**
 * Retrieve evaluated and ranked deployment candidates for a screening run.
 * (GET /api/v1/runs/{run_id}/candidates)
 */
export async function getRunCandidates(
  runId: string,
  limit = 20,
  offset = 0
): Promise<CandidateResultsResponse> {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  return request<CandidateResultsResponse>(
    `/api/v1/runs/${encodeURIComponent(runId)}/candidates?${query.toString()}`,
    {
      method: 'GET',
    }
  )
}
