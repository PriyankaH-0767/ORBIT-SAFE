import { request } from './client'

/**
 * Response from the canonical deterministic demo run endpoint.
 * The frontend should use run_id with existing /runs/* APIs for full results.
 */
export interface DemoRunResponse {
  run_id: string
  status: string
  demo: boolean
  message: string
  data_source: string
  reference_frame: string
  time_scale: string
}

/**
 * Obtain the canonical deterministic demo run (GET /api/v1/demo/run).
 *
 * On backend first-call this may take ~90 s while the pipeline executes.
 * On subsequent calls (or if the run was pre-warmed at startup) this returns instantly.
 */
export async function getDemoRun(): Promise<DemoRunResponse> {
  return request<DemoRunResponse>('/api/v1/demo/run', { method: 'GET' })
}
