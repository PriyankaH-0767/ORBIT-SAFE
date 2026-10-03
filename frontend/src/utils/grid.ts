export const MAX_CANDIDATES = 300

export interface CandidateGridParams {
  altitude_min_km: number
  altitude_max_km: number
  altitude_step_km: number
  inclination_min_deg: number
  inclination_max_deg: number
  inclination_step_deg: number
  delay_min_minutes: number
  delay_max_minutes: number
  delay_step_minutes: number
}

export function calculateCandidateCount(params: CandidateGridParams): {
  count: number
  nAlt: number
  nInc: number
  nDelay: number
  isValid: boolean
} {
  const {
    altitude_min_km,
    altitude_max_km,
    altitude_step_km,
    inclination_min_deg,
    inclination_max_deg,
    inclination_step_deg,
    delay_min_minutes,
    delay_max_minutes,
    delay_step_minutes,
  } = params

  if (
    altitude_step_km <= 0 ||
    inclination_step_deg <= 0 ||
    delay_step_minutes <= 0 ||
    altitude_min_km > altitude_max_km ||
    inclination_min_deg > inclination_max_deg ||
    delay_min_minutes > delay_max_minutes
  ) {
    return { count: 0, nAlt: 0, nInc: 0, nDelay: 0, isValid: false }
  }

  const nAlt = Math.floor((altitude_max_km - altitude_min_km) / altitude_step_km + 1e-9) + 1
  const nInc = Math.floor((inclination_max_deg - inclination_min_deg) / inclination_step_deg + 1e-9) + 1
  const nDelay = Math.floor((delay_max_minutes - delay_min_minutes) / delay_step_minutes + 1e-9) + 1
  const count = nAlt * nInc * nDelay

  return { count, nAlt, nInc, nDelay, isValid: count > 0 }
}
