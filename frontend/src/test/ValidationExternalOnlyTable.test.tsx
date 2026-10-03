import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ValidationExternalOnlyTable } from '../components/results/ValidationExternalOnlyTable'
import type { ValidationExternalOnlyEvent } from '../types/validation'

describe('ValidationExternalOnlyTable Component (Phase P23)', () => {
  const mockExternalOnlyEvents: ValidationExternalOnlyEvent[] = [
    {
      external_event_id: 'SOC-REF-777',
      candidate_identifier: 'PRIMARY-SAT-A',
      debris_norad_id: '99001',
      tca: '2026-10-17T11:00:00Z',
      miss_distance_km: 2.1,
      relative_velocity_km_s: 14.8,
      notes: 'Unmatched in evaluated candidate screening envelope.',
    },
  ]

  it('1. renders external-only events table with neutral styling', () => {
    render(<ValidationExternalOnlyTable events={mockExternalOnlyEvents} />)

    expect(screen.getByText('SOC-REF-777')).toBeInTheDocument()
    expect(screen.getByText('PRIMARY-SAT-A')).toBeInTheDocument()
    expect(screen.getByText('NORAD 99001')).toBeInTheDocument()
    expect(screen.getByText('2.10 km')).toBeInTheDocument()
    expect(screen.getByText('14.80 km/s')).toBeInTheDocument()
    expect(screen.getByText(/unmatched in evaluated candidate/i)).toBeInTheDocument()
  })

  it('2. renders empty state notice when list is empty', () => {
    render(<ValidationExternalOnlyTable events={[]} />)

    expect(
      screen.getByText(/no external-only reference events in this comparison/i)
    ).toBeInTheDocument()
  })
})
