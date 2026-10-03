/**
 * TypeScript types for Phase P22 3D Globe Visualization.
 * Aligns strictly with backend P15 schemas from backend/app/schemas/globe.py.
 *
 * Frame: TEME (True Equator Mean Equinox).
 * Position units: km.
 * Velocity units: km/s.
 * Time scale: UTC.
 */

export interface GlobeStatePoint {
  t: string // UTC ISO 8601
  x_km: number
  y_km: number
  z_km: number
  vx_km_s: number
  vy_km_s: number
  vz_km_s: number
}

export interface GlobeCandidateTrack {
  candidate_id: string
  rank?: number | null
  altitude_km: number
  inclination_deg: number
  raan_deg: number
  risk_score: number
  within_dv_budget: boolean
  deployment_delay_minutes: number
  deployment_epoch: string
  trajectory_start: string
  trajectory_end: string
  point_count: number
  trajectory: GlobeStatePoint[]
}

export interface GlobeDebrisTrack {
  norad_id: string
  object_name: string
  debris_db_id?: string | null
  point_count: number
  trajectory: GlobeStatePoint[]
}

export interface GlobeEventMarker {
  event_id: string
  candidate_id?: string | null
  debris_object_id?: string | null
  debris_norad_id?: string | null
  tca: string // UTC ISO 8601
  miss_distance_km: number
  relative_velocity_km_s: number
  x_km: number
  y_km: number
  z_km: number
}

export interface GlobeResponse {
  run_id: string
  status: string
  frame: string // "TEME"
  time_scale: string // "UTC"
  sample_step_seconds: number
  epoch_start: string
  epoch_end: string
  candidate_count: number
  debris_count: number
  event_count: number
  candidates: GlobeCandidateTrack[]
  debris: GlobeDebrisTrack[]
  events: GlobeEventMarker[]
}

export interface GlobeRequestOptions {
  candidate_ids?: string[]
  sample_step_seconds?: number
  max_candidates?: number
  max_debris?: number
}
