import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CandidateDetailPanel } from '../components/results/CandidateDetailPanel'
import type { CandidateResultItem } from '../types/candidate'

const mockCandidate: CandidateResultItem = {
  candidate_id: 'cand-042',
  altitude_km: 550.25,
  inclination_deg: 97.5,
  raan_deg: 180.25,
  u0_deg: 45.1,
  deployment_delay_minutes: 20.0,
  deployment_epoch: '2026-10-04T12:20:00Z',
  delta_v_m_s: 48.75,
  propellant_mass_kg: 3.821,
  fuel_fraction: 0.0382,
  within_dv_budget: true,
  risk_score: 14.8,
  accepted_event_count: 3,
  minimum_miss_distance_km: 6.42,
  uncertainty_level: 'nominal',
  rank: 1,
}

describe('CandidateDetailPanel Component', () => {
  it('renders all required candidate fields accurately without altering values', () => {
    render(<CandidateDetailPanel candidate={mockCandidate} onClose={vi.fn()} />)

    expect(screen.getByText('Rank 1')).toBeInTheDocument()
    expect(screen.getByText('Candidate: cand-042')).toBeInTheDocument()
    expect(screen.getByText('550.25 km')).toBeInTheDocument()
    expect(screen.getAllByText('97.50°').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('180.25°')).toBeInTheDocument()
    expect(screen.getByText('45.10°')).toBeInTheDocument()
    expect(screen.getAllByText('20.0 min').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('48.75 m/s')).toBeInTheDocument()
    expect(screen.getByText('3.821 kg')).toBeInTheDocument()
    expect(screen.getByText('3.82%')).toBeInTheDocument()
    expect(screen.getByText('Within Budget')).toBeInTheDocument()
    expect(screen.getByText('14.8 / 100')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('6.42 km')).toBeInTheDocument()
    expect(screen.getByText('nominal')).toBeInTheDocument()

    // Phase P25 Section G: Candidate Explanation Panel
    expect(screen.getByText('Why is this candidate ranked here?')).toBeInTheDocument()
    expect(screen.getByText(/relatively low/i)).toBeInTheDocument()
    expect(screen.getByText(/estimated propulsion demand within the configured budget/i)).toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', () => {
    const handleClose = vi.fn()
    render(<CandidateDetailPanel candidate={mockCandidate} onClose={handleClose} />)

    const closeBtn = screen.getByRole('button', { name: /Close detail panel/i })
    fireEvent.click(closeBtn)
    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it('renders nothing when candidate is null', () => {
    const { container } = render(<CandidateDetailPanel candidate={null} onClose={vi.fn()} />)
    expect(container.firstChild).toBeNull()
  })
})
