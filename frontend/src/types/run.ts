/**
 * Screening Run types according to D-DATO Frozen API Contract (P18).
 */

export type RunLifecycleStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface RunStatusResponse {
  run_id: string
  plan_id: string
  status: RunLifecycleStatus | string
  progress_percent: number
  current_stage: string | null
  message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  candidate_count: number
  conjunction_event_count: number
  ranked_candidate_count: number
}

export interface PlanRunsResponse {
  plan_id: string
  runs: RunStatusResponse[]
  total: number
}
