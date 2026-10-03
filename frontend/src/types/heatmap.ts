/**
 * Heatmap types according to D-DATO Frozen API Contract (P14/P18/P21).
 */

export interface HeatmapCell {
  candidate_id: string
  altitude_km: number
  inclination_deg: number
  delay_minutes: number
  risk_score?: number | null
  rank?: number | null
  delta_v_m_s?: number | null
  within_dv_budget?: boolean | null
  accepted_event_count?: number | null
  minimum_miss_distance_km?: number | null
  uncertainty_level?: string | null
}

export interface HeatmapLayer {
  inclination_deg: number
  altitude_values_km: number[]
  delay_values_minutes: number[]
  values: (number | null)[][]
  cells: HeatmapCell[]
}

export interface HeatmapResponse {
  run_id: string
  status: string
  metric: string
  x_axis: string
  y_axis: string
  inclination_values_deg: number[]
  layers: HeatmapLayer[]
  total_candidates: number
  populated_cells: number
  min_risk_score?: number | null
  max_risk_score?: number | null
}
