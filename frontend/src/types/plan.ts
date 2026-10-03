/**
 * Mission Plan types according to D-DATO Frozen API Contract (P18).
 */

export type DataSourceType = 'celestrak' | 'spacetrack'

export interface PlanCreateRequest {
  epoch_start?: string
  altitude_min_km: number
  altitude_max_km: number
  altitude_step_km: number
  inclination_min_deg: number
  inclination_max_deg: number
  inclination_step_deg: number
  raan_deg: number
  u0_deg: number
  delay_min_minutes: number
  delay_max_minutes: number
  delay_step_minutes: number
  raan_delay_coupling_deg_per_min: number
  screening_days: number
  reference_altitude_km: number
  reference_inclination_deg: number
  dv_budget_m_s: number
  spacecraft_mass_kg: number
  isp_seconds: number
  fuel_weight: number
  risk_weight: number
  data_source: DataSourceType
  demo_mode: boolean
}

export const DEFAULT_PLAN_FORM: PlanCreateRequest = {
  epoch_start: '',
  altitude_min_km: 500.0,
  altitude_max_km: 600.0,
  altitude_step_km: 25.0,
  inclination_min_deg: 97.0,
  inclination_max_deg: 98.0,
  inclination_step_deg: 0.5,
  raan_deg: 0.0,
  u0_deg: 0.0,
  delay_min_minutes: 0.0,
  delay_max_minutes: 720.0,
  delay_step_minutes: 60.0,
  raan_delay_coupling_deg_per_min: 0.25068,
  screening_days: 3,
  reference_altitude_km: 550.0,
  reference_inclination_deg: 97.5,
  dv_budget_m_s: 100.0,
  spacecraft_mass_kg: 3.0,
  isp_seconds: 60.0,
  fuel_weight: 0.4,
  risk_weight: 0.6,
  data_source: 'celestrak',
  demo_mode: true,
}

export interface PlanRunAcceptedResponse {
  plan_id: string
  run_id: string
  status: string
  message: string
  created_at: string
}

export interface PlanResponse {
  plan_id: string
  created_at: string
  updated_at: string
  epoch_start: string
  altitude_min_km: number
  altitude_max_km: number
  altitude_step_km: number
  inclination_min_deg: number
  inclination_max_deg: number
  inclination_step_deg: number
  raan_deg: number
  u0_deg: number
  delay_min_minutes: number
  delay_max_minutes: number
  delay_step_minutes: number
  raan_delay_coupling_deg_per_min: number
  screening_days: number
  reference_altitude_km: number
  reference_inclination_deg: number
  dv_budget_m_s: number
  spacecraft_mass_kg: number
  isp_seconds: number
  fuel_weight: number
  risk_weight: number
  data_source: DataSourceType
  demo_mode: boolean
}
