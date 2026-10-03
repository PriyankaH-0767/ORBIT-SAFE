import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CandidatePreview } from '../components/planner/CandidatePreview'
import { calculateCandidateCount, MAX_CANDIDATES } from '../utils/grid'

describe('CandidatePreview & Grid Calculation', () => {
  it('calculates the default grid size as 195 candidates (5 x 3 x 13)', () => {
    const defaultParams = {
      altitude_min_km: 500.0,
      altitude_max_km: 600.0,
      altitude_step_km: 25.0,
      inclination_min_deg: 97.0,
      inclination_max_deg: 98.0,
      inclination_step_deg: 0.5,
      delay_min_minutes: 0.0,
      delay_max_minutes: 720.0,
      delay_step_minutes: 60.0,
    }

    const { count, nAlt, nInc, nDelay, isValid } = calculateCandidateCount(defaultParams)
    expect(isValid).toBe(true)
    expect(nAlt).toBe(5)
    expect(nInc).toBe(3)
    expect(nDelay).toBe(13)
    expect(count).toBe(195)
  })

  it('renders estimated candidate count within limit', () => {
    const defaultParams = {
      altitude_min_km: 500.0,
      altitude_max_km: 600.0,
      altitude_step_km: 25.0,
      inclination_min_deg: 97.0,
      inclination_max_deg: 98.0,
      inclination_step_deg: 0.5,
      delay_min_minutes: 0.0,
      delay_max_minutes: 720.0,
      delay_step_minutes: 60.0,
    }

    render(<CandidatePreview params={defaultParams} />)

    expect(screen.getByText('Candidate Grid Preview')).toBeInTheDocument()
    expect(screen.getByText(`195 / ${MAX_CANDIDATES}`)).toBeInTheDocument()
    expect(screen.queryByText(/exceeding the backend maximum limit/i)).not.toBeInTheDocument()
  })

  it('identifies when grid size exceeds the 300 maximum limit and renders warning', () => {
    const oversizedParams = {
      altitude_min_km: 400.0,
      altitude_max_km: 800.0,
      altitude_step_km: 10.0, // 41
      inclination_min_deg: 90.0,
      inclination_max_deg: 100.0,
      inclination_step_deg: 1.0, // 11
      delay_min_minutes: 0.0,
      delay_max_minutes: 60.0,
      delay_step_minutes: 30.0, // 3
    } // 41 * 11 * 3 = 1353

    const { count, isValid } = calculateCandidateCount(oversizedParams)
    expect(isValid).toBe(true)
    expect(count).toBeGreaterThan(300)

    render(<CandidatePreview params={oversizedParams} />)

    expect(screen.getByText(new RegExp(`${count} / ${MAX_CANDIDATES}`))).toBeInTheDocument()
    expect(screen.getByText(/exceeding the backend maximum limit of 300/i)).toBeInTheDocument()
  })

  it('handles invalid step or min > max gracefully', () => {
    const invalidParams = {
      altitude_min_km: 600.0,
      altitude_max_km: 500.0, // min > max
      altitude_step_km: 25.0,
      inclination_min_deg: 97.0,
      inclination_max_deg: 98.0,
      inclination_step_deg: 0.5,
      delay_min_minutes: 0.0,
      delay_max_minutes: 60.0,
      delay_step_minutes: 0.0, // invalid step
    }

    const { count, isValid } = calculateCandidateCount(invalidParams)
    expect(isValid).toBe(false)
    expect(count).toBe(0)
  })
})
