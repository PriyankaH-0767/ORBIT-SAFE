/**
 * Conjunction Event types according to D-DATO Frozen API Contract (P18/P20).
 */

export interface EventResultItem {
  id?: string | null
  candidate_id?: string | null
  debris_object_id?: string | null
  debris_norad_id?: string | null
  debris_name?: string | null
  tca: string
  miss_distance_km: number
  relative_velocity_km_s: number
  threshold_km: number
  screening_source: string
}

export interface EventResultsResponse {
  run_id: string
  total: number
  limit: number
  offset: number
  event_count?: number | null
  status?: string | null
  events: EventResultItem[]
}
