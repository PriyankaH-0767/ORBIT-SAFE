import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CandidateTable } from '../components/results/CandidateTable'
import type { CandidateResultItem } from '../types/candidate'

const mockCandidates: CandidateResultItem[] = [
  {
    candidate_id: 'cand-001',
    altitude_km: 500.5,
    inclination_deg: 97.42,
    raan_deg: 120.0,
    u0_deg: 45.0,
    deployment_delay_minutes: 15.0,
    deployment_epoch: '2026-10-04T12:15:00Z',
    delta_v_m_s: 42.15,
    propellant_mass_kg: 3.25,
    fuel_fraction: 0.0325,
    within_dv_budget: true,
    risk_score: 12.4,
    accepted_event_count: 2,
    minimum_miss_distance_km: 8.75,
    uncertainty_level: 'nominal',
    rank: 1,
  },
  {
    candidate_id: 'cand-002',
    altitude_km: 550.0,
    inclination_deg: 98.1,
    raan_deg: 125.0,
    u0_deg: 50.0,
    deployment_delay_minutes: 30.0,
    deployment_epoch: '2026-10-04T12:30:00Z',
    delta_v_m_s: 65.8,
    propellant_mass_kg: 5.1,
    fuel_fraction: 0.051,
    within_dv_budget: false,
    risk_score: 28.7,
    accepted_event_count: 0,
    minimum_miss_distance_km: null, // null miss distance
    uncertainty_level: 'low',
    rank: 2,
  },
]

describe('CandidateTable Component', () => {
  it('renders backend candidate fields with accurate columns and formatting', () => {
    render(
      <CandidateTable
        candidates={mockCandidates}
        onSelectCandidate={vi.fn()}
      />
    )

    // Ranks
    expect(screen.getByText('Rank 1')).toBeInTheDocument()
    expect(screen.getByText('Rank 2')).toBeInTheDocument()

    // Candidate IDs
    expect(screen.getByText('cand-001')).toBeInTheDocument()
    expect(screen.getByText('cand-002')).toBeInTheDocument()

    // Numeric fields
    expect(screen.getByText('500.5')).toBeInTheDocument()
    expect(screen.getByText('97.42')).toBeInTheDocument()
    expect(screen.getByText('15.0')).toBeInTheDocument()
    expect(screen.getByText('42.15')).toBeInTheDocument()
    expect(screen.getByText('12.4')).toBeInTheDocument()
    expect(screen.getByText('8.75')).toBeInTheDocument()

    // Budget badges
    expect(screen.getByText('OK')).toBeInTheDocument()
    expect(screen.getByText('Exceeded')).toBeInTheDocument()
  })

  it('displays units in column headers correctly', () => {
    render(
      <CandidateTable
        candidates={mockCandidates}
        onSelectCandidate={vi.fn()}
      />
    )

    expect(screen.getByText('Altitude (km)')).toBeInTheDocument()
    expect(screen.getByText('Inclination (°)')).toBeInTheDocument()
    expect(screen.getByText('Delay (min)')).toBeInTheDocument()
    expect(screen.getByText('Delta-V (m/s)')).toBeInTheDocument()
    expect(screen.getByText('Min Miss (km)')).toBeInTheDocument()
  })

  it('displays "—" when minimum miss distance is null', () => {
    render(
      <CandidateTable
        candidates={mockCandidates}
        onSelectCandidate={vi.fn()}
      />
    )

    // cand-002 has null minimum_miss_distance_km
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThan(0)
  })

  it('triggers onSelectCandidate callback on row click', () => {
    const handleSelect = vi.fn()
    render(
      <CandidateTable
        candidates={mockCandidates}
        onSelectCandidate={handleSelect}
      />
    )

    fireEvent.click(screen.getByText('cand-001'))
    expect(handleSelect).toHaveBeenCalledWith(mockCandidates[0])
  })

  it('shows loading indicator when isLoading is true and candidates are empty', () => {
    render(
      <CandidateTable
        candidates={[]}
        isLoading={true}
        onSelectCandidate={vi.fn()}
      />
    )

    expect(screen.getByText(/Loading ranked candidates…/i)).toBeInTheDocument()
  })
})
