/**
 * Candidate Orbit types according to D-DATO Frozen API Contract (P18/P20).
 */

export interface CandidateResultItem {
  candidate_id: string
  altitude_km: number
  inclination_deg: number
  raan_deg: number
  u0_deg: number
  deployment_delay_minutes: number
  deployment_epoch?: string | null
  delta_v_m_s: number
  propellant_mass_kg: number
  fuel_fraction: number
  within_dv_budget: boolean
  risk_score: number
  accepted_event_count?: number | null
  minimum_miss_distance_km?: number | null
  uncertainty_level?: string | null
  normalized_fuel_cost?: number | null
  normalized_risk_cost?: number | null
  composite_score?: number | null
  rank?: number | null
}

export interface CandidateResultsResponse {
  run_id: string
  total: number
  limit: number
  offset: number
  candidate_count?: number | null
  status?: string | null
  candidates: CandidateResultItem[]
}
