import { request } from './client'
import type { ValidationResponse, ValidationExecutionRequest } from '../types/validation'

/**
 * Default parameters for external reference validation.
 * source: "socrates"
 * tca_tolerance_seconds: 300.0 (5 minutes)
 * miss_distance_tolerance_km: 5.0 km
 * demo_mode: true
 */
export const DEFAULT_VALIDATION_REQUEST: ValidationExecutionRequest = {
  source: 'socrates',
  tca_tolerance_seconds: 300.0,
  miss_distance_tolerance_km: 5.0,
  demo_mode: true,
}

/**
 * Execute an external reference validation comparison for a completed screening run.
 * (POST /api/v1/runs/{run_id}/validation)
 *
 * @param runId Unique screening run identifier
 * @param executionRequest Optional tolerance parameters and source
 */
export async function createValidation(
  runId: string,
  executionRequest?: ValidationExecutionRequest
): Promise<ValidationResponse> {
  const payload = {
    ...DEFAULT_VALIDATION_REQUEST,
    ...executionRequest,
  }

  return request<ValidationResponse>(
    `/api/v1/runs/${encodeURIComponent(runId)}/validation`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  )
}

/**
 * Retrieve the latest persisted external reference validation report for a screening run.
 * (GET /api/v1/runs/{run_id}/validation)
 *
 * Strictly read-only; reads persisted report from DB without triggering comparison.
 *
 * @param runId Unique screening run identifier
 */
export async function getRunValidation(runId: string): Promise<ValidationResponse> {
  return request<ValidationResponse>(
    `/api/v1/runs/${encodeURIComponent(runId)}/validation`,
    {
      method: 'GET',
    }
  )
}

/**
 * Retrieve a specific persisted validation report by its unique ID.
 * (GET /api/v1/validations/{validation_id})
 *
 * Strictly read-only.
 *
 * @param validationId Unique validation report identifier
 */
export async function getValidation(validationId: string): Promise<ValidationResponse> {
  return request<ValidationResponse>(
    `/api/v1/validations/${encodeURIComponent(validationId)}`,
    {
      method: 'GET',
    }
  )
}
