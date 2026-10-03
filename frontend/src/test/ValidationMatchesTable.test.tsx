import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ValidationMatchesTable } from '../components/results/ValidationMatchesTable'
import type { ValidationMatch } from '../types/validation'

describe('ValidationMatchesTable Component (Phase P23)', () => {
  const mockMatches: ValidationMatch[] = [
    {
      d_dato_event_id: 'dd-evt-1111-2222',
      external_event_id: 'SOC-999',
      candidate_id: 'cand-001',
      debris_norad_id: '25544',
      tca_d_dato: '2026-10-15T18:42:15Z',
      tca_external: '2026-10-15T18:42:10Z',
      tca_error_seconds: 5.0,
      miss_distance_d_dato_km: 4.12,
      miss_distance_external_km: 4.25,
      miss_distance_difference_km: -0.13,
      match_criteria: ['norad_id', 'tca_tolerance'],
    },
  ]

  it('1. renders table with matched event details and criteria tags', () => {
    render(<ValidationMatchesTable matches={mockMatches} />)

    expect(screen.getByText(/dd-evt-1/i)).toBeInTheDocument()
    expect(screen.getByText('SOC-999')).toBeInTheDocument()
    expect(screen.getByText(/cand-001/i)).toBeInTheDocument()
    expect(screen.getByText('NORAD 25544')).toBeInTheDocument()
    expect(screen.getByText('+5.0 s')).toBeInTheDocument()
    expect(screen.getByText('4.12 km')).toBeInTheDocument()
    expect(screen.getByText('4.25 km')).toBeInTheDocument()
    expect(screen.getByText('-0.13 km')).toBeInTheDocument()
    expect(screen.getByText('norad_id')).toBeInTheDocument()
    expect(screen.getByText('tca_tolerance')).toBeInTheDocument()
  })

  it('2. triggers onSelectCandidateId when candidate ID button is clicked', () => {
    const mockSelect = vi.fn()
    render(<ValidationMatchesTable matches={mockMatches} onSelectCandidateId={mockSelect} />)

    const candBtn = screen.getByRole('button', { name: /cand-001/i })
    fireEvent.click(candBtn)

    expect(mockSelect).toHaveBeenCalledTimes(1)
    expect(mockSelect).toHaveBeenCalledWith('cand-001')
  })

  it('3. renders empty state notice when matches list is empty', () => {
    render(<ValidationMatchesTable matches={[]} />)

    expect(
      screen.getByText(/no matched reference events were identified within the configured tolerances/i)
    ).toBeInTheDocument()
  })
})
