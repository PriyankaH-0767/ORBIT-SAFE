import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ValidationDdatoOnlyTable } from '../components/results/ValidationDdatoOnlyTable'
import type { ValidationDdatoOnlyEvent } from '../types/validation'

describe('ValidationDdatoOnlyTable Component (Phase P23)', () => {
  const mockDdatoOnlyEvents: ValidationDdatoOnlyEvent[] = [
    {
      d_dato_event_id: 'dd-solo-1234-5678',
      candidate_id: 'cand-009',
      debris_norad_id: '40001',
      tca: '2026-10-16T04:12:00Z',
      miss_distance_km: 18.5,
      relative_velocity_km_s: 11.2,
      notes: 'No matching external reference event within configured tolerances.',
    },
  ]

  it('1. renders D-DATO-only events table', () => {
    render(<ValidationDdatoOnlyTable events={mockDdatoOnlyEvents} />)

    expect(screen.getByText(/dd-solo-/i)).toBeInTheDocument()
    expect(screen.getByText(/cand-009/i)).toBeInTheDocument()
    expect(screen.getByText('NORAD 40001')).toBeInTheDocument()
    expect(screen.getByText('18.50 km')).toBeInTheDocument()
    expect(screen.getByText('11.20 km/s')).toBeInTheDocument()
  })

  it('2. triggers onSelectCandidateId when candidate ID button is clicked', () => {
    const mockSelect = vi.fn()
    render(<ValidationDdatoOnlyTable events={mockDdatoOnlyEvents} onSelectCandidateId={mockSelect} />)

    const candBtn = screen.getByRole('button', { name: /cand-009/i })
    fireEvent.click(candBtn)

    expect(mockSelect).toHaveBeenCalledTimes(1)
    expect(mockSelect).toHaveBeenCalledWith('cand-009')
  })

  it('3. renders empty state notice when list is empty', () => {
    render(<ValidationDdatoOnlyTable events={[]} />)

    expect(
      screen.getByText(/no d-dato-only events in this comparison/i)
    ).toBeInTheDocument()
  })
})
