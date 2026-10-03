/**
 * TypeScript types for Phase P23 External Conjunction Screening Validation.
 * Aligns strictly with backend P16 schemas from backend/app/schemas/validation.py.
 *
 * NON-OPERATIONAL DISCLAIMER:
 * D-DATO validation comparison is external reference evidence only.
 * It does NOT represent certified flight safety, operational conjunction assessment,
 * true collision probability, CDM generation, maneuver planning, or launch COLA.
 */

export interface ValidationMatch {
  d_dato_event_id?: string | null
  external_event_id?: string | null
  candidate_id?: string | null
  debris_norad_id?: string | null
  tca_d_dato?: string | null
  tca_external?: string | null
  tca_error_seconds?: number | null
  miss_distance_d_dato_km?: number | null
  miss_distance_external_km?: number | null
  miss_distance_difference_km?: number | null
  match_criteria: string[]
}

export interface ValidationDdatoOnlyEvent {
  d_dato_event_id: string
  candidate_id?: string | null
  debris_norad_id?: string | null
  tca?: string | null
  miss_distance_km?: number | null
  relative_velocity_km_s?: number | null
  notes?: string | null
}

export interface ValidationExternalOnlyEvent {
  external_event_id: string
  debris_norad_id?: string | null
  tca?: string | null
  miss_distance_km?: number | null
  relative_velocity_km_s?: number | null
  candidate_identifier?: string | null
  notes?: string | null
}

export interface ValidationSummary {
  d_dato_event_count: number
  external_event_count: number
  matched_event_count: number
  d_dato_only_count: number
  external_only_count: number
  external_coverage_percent?: number | null
  d_dato_match_rate_percent?: number | null
  mean_abs_tca_error_seconds?: number | null
  max_abs_tca_error_seconds?: number | null
  mean_abs_miss_distance_difference_km?: number | null
  max_abs_miss_distance_difference_km?: number | null
}

export interface ValidationResponse {
  validation_id: string
  run_id: string
  status: string
  source: string
  source_fetched_at?: string | null
  validation_created_at: string
  summary: ValidationSummary
  matches: ValidationMatch[]
  d_dato_only: ValidationDdatoOnlyEvent[]
  external_only: ValidationExternalOnlyEvent[]
  notes: string[]
}

export interface ValidationExecutionRequest {
  source?: string
  tca_tolerance_seconds?: number
  miss_distance_tolerance_km?: number
  demo_mode?: boolean
}
