import { request } from './client'
import type { PlanCreateRequest, PlanRunAcceptedResponse, PlanResponse } from '../types/plan'
import type { PlanRunsResponse } from '../types/run'

/**
 * Submit a mission plan and queue asynchronous screening (POST /api/v1/plans -> 202 Accepted)
 */
export async function createPlan(plan: PlanCreateRequest): Promise<PlanRunAcceptedResponse> {
  return request<PlanRunAcceptedResponse>('/api/v1/plans', {
    method: 'POST',
    body: JSON.stringify(plan),
  })
}

/**
 * Retrieve persisted mission planning parameters (GET /api/v1/plans/{plan_id})
 */
export async function getPlan(planId: string): Promise<PlanResponse> {
  return request<PlanResponse>(`/api/v1/plans/${encodeURIComponent(planId)}`, {
    method: 'GET',
  })
}

/**
 * Retrieve execution run history for a plan (GET /api/v1/plans/{plan_id}/runs)
 */
export async function getPlanRuns(planId: string): Promise<PlanRunsResponse> {
  return request<PlanRunsResponse>(`/api/v1/plans/${encodeURIComponent(planId)}/runs`, {
    method: 'GET',
  })
}
