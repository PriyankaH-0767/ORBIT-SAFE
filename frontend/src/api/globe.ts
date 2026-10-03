import { request } from './client'
import type { GlobeResponse, GlobeRequestOptions } from '../types/globe'

/**
 * Default bounded query parameters for initial 3D globe visualization.
 * sample_step_seconds = 300 (5 minutes)
 * max_candidates = 5
 * max_debris = 10
 */
export const DEFAULT_GLOBE_OPTIONS: GlobeRequestOptions = {
  sample_step_seconds: 300,
  max_candidates: 5,
  max_debris: 10,
}

/**
 * Retrieve 3D orbital trajectory data for a screening run.
 * (GET /api/v1/runs/{run_id}/globe)
 *
 * All coordinates returned are in the TEME frame (km).
 *
 * @param runId Unique screening run identifier
 * @param options Query parameters: candidate_ids, sample_step_seconds, max_candidates, max_debris
 */
export async function getRunGlobe(
  runId: string,
  options?: GlobeRequestOptions
): Promise<GlobeResponse> {
  const query = new URLSearchParams()

  if (options?.candidate_ids && options.candidate_ids.length > 0) {
    const validIds = options.candidate_ids.map((id) => id.trim()).filter(Boolean)
    if (validIds.length > 0) {
      query.set('candidate_ids', validIds.join(','))
    }
  }

  if (options?.sample_step_seconds != null) {
    query.set('sample_step_seconds', String(options.sample_step_seconds))
  }

  if (options?.max_candidates != null) {
    query.set('max_candidates', String(options.max_candidates))
  }

  if (options?.max_debris != null) {
    query.set('max_debris', String(options.max_debris))
  }

  const queryString = query.toString() ? `?${query.toString()}` : ''
  return request<GlobeResponse>(
    `/api/v1/runs/${encodeURIComponent(runId)}/globe${queryString}`,
    {
      method: 'GET',
    }
  )
}
