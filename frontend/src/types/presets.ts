import type { PlanCreateRequest } from './plan'

export interface MissionPreset {
  id: string
  name: string
  label: string
  tag: string
  description: string
  altitudeRange: string
  inclinationRange: string
  delayRange: string
  purpose: string
  values: Partial<PlanCreateRequest>
}

export const MISSION_PRESETS: MissionPreset[] = [
  {
    id: 'sso_demo',
    name: 'High-Inclination LEO / SSO-Style Screening',
    label: 'High-Inclination LEO (500–600 km)',
    tag: 'Deterministic Demo',
    description: 'High-inclination polar orbit screening across a typical 500–600 km Earth observation corridor.',
    altitudeRange: '500 – 600 km (step 25 km)',
    inclinationRange: '97.0° – 98.0° (step 0.5°)',
    delayRange: '0 – 720 min (step 60 min)',
    purpose: 'Evaluates 195 candidate orbits against cataloged high-inclination debris clusters with deterministic fixtures.',
    values: {
      altitude_min_km: 500.0,
      altitude_max_km: 600.0,
      altitude_step_km: 25.0,
      inclination_min_deg: 97.0,
      inclination_max_deg: 98.0,
      inclination_step_deg: 0.5,
      delay_min_minutes: 0.0,
      delay_max_minutes: 720.0,
      delay_step_minutes: 60.0,
      screening_days: 3,
      reference_altitude_km: 550.0,
      reference_inclination_deg: 97.5,
      dv_budget_m_s: 100.0,
      spacecraft_mass_kg: 3.0,
      isp_seconds: 60.0,
      fuel_weight: 0.4,
      risk_weight: 0.6,
      demo_mode: true,
      data_source: 'celestrak',
    },
  },
  {
    id: 'low_leo',
    name: 'Low LEO Screening',
    label: 'Low LEO Corridor (400–500 km)',
    tag: 'High Drag / Mid-Inc',
    description: 'Mid-inclination deployment corridor near the ISS altitude band with shorter screening duration.',
    altitudeRange: '400 – 500 km (step 25 km)',
    inclinationRange: '51.6° – 52.0° (step 0.2°)',
    delayRange: '0 – 360 min (step 60 min)',
    purpose: 'Evaluates 105 candidate orbits in a lower-altitude, mid-inclination regime.',
    values: {
      altitude_min_km: 400.0,
      altitude_max_km: 500.0,
      altitude_step_km: 25.0,
      inclination_min_deg: 51.6,
      inclination_max_deg: 52.0,
      inclination_step_deg: 0.2,
      delay_min_minutes: 0.0,
      delay_max_minutes: 360.0,
      delay_step_minutes: 60.0,
      screening_days: 2,
      reference_altitude_km: 450.0,
      reference_inclination_deg: 51.8,
      dv_budget_m_s: 80.0,
      spacecraft_mass_kg: 3.0,
      isp_seconds: 60.0,
      fuel_weight: 0.5,
      risk_weight: 0.5,
      demo_mode: true,
      data_source: 'celestrak',
    },
  },
  {
    id: 'custom',
    name: 'Custom Mission',
    label: 'Custom Mission Parameters',
    tag: 'Manual Configuration',
    description: 'Freely customize orbital geometry, delta-V limits, screening duration, and multi-objective weights.',
    altitudeRange: 'User-specified bounds',
    inclinationRange: 'User-specified bounds',
    delayRange: 'User-specified bounds',
    purpose: 'Interactive exploration of arbitrary CubeSat deployment search spaces up to the 300-candidate cap.',
    values: {},
  },
]
