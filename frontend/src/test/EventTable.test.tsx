import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EventTable } from '../components/results/EventTable'
import { formatTCAtoUTC } from '../utils/date'
import type { EventResultItem } from '../types/event'

const mockEvents: EventResultItem[] = [
  {
    id: 'evt-001',
    candidate_id: 'cand-001',
    debris_object_id: 'deb-12345',
    debris_norad_id: '25544',
    debris_name: 'FENGYUN 1C DEB',
    tca: '2026-10-04T03:29:28.000Z',
    miss_distance_km: 1.45,
    relative_velocity_km_s: 14.28,
    threshold_km: 25.0,
    screening_source: 'sgp4_tle',
  },
  {
    id: 'evt-002',
    candidate_id: 'cand-002',
    debris_object_id: 'deb-67890',
    debris_norad_id: '39088',
    debris_name: 'COSMOS 2251 DEB',
    tca: '2026-10-04T08:12:44.000Z',
    miss_distance_km: 4.82,
    relative_velocity_km_s: 11.55,
    threshold_km: 25.0,
    screening_source: 'sgp4_tle',
  },
]

describe('EventTable Component', () => {
  it('formats TCA ISO strings to readable UTC format', () => {
    const formatted = formatTCAtoUTC('2026-10-04T03:29:28.000Z')
    expect(formatted).toBe('2026-10-04 03:29:28 UTC')
  })

  it('renders backend conjunction event fields accurately', () => {
    render(
      <EventTable
        events={mockEvents}
        onSelectEvent={vi.fn()}
      />
    )

    // Formatted UTC timestamps
    expect(screen.getByText('2026-10-04 03:29:28 UTC')).toBeInTheDocument()
    expect(screen.getByText('2026-10-04 08:12:44 UTC')).toBeInTheDocument()

    // Candidates
    expect(screen.getByText('cand-001')).toBeInTheDocument()
    expect(screen.getByText('cand-002')).toBeInTheDocument()

    // NORAD IDs
    expect(screen.getByText('25544')).toBeInTheDocument()
    expect(screen.getByText('39088')).toBeInTheDocument()

    // Miss distance & rel velocity
    expect(screen.getByText('1.45 km')).toBeInTheDocument()
    expect(screen.getByText('14.28 km/s')).toBeInTheDocument()
    expect(screen.getByText('4.82 km')).toBeInTheDocument()
    expect(screen.getByText('11.55 km/s')).toBeInTheDocument()

    // Sources
    expect(screen.getAllByText('sgp4_tle')).toHaveLength(2)
  })

  it('triggers onSelectEvent when a row is clicked', () => {
    const handleSelectEvent = vi.fn()
    render(
      <EventTable
        events={mockEvents}
        onSelectEvent={handleSelectEvent}
      />
    )

    fireEvent.click(screen.getByText('25544'))
    expect(handleSelectEvent).toHaveBeenCalledWith(mockEvents[0])
  })

  it('triggers onSelectCandidateId when candidate ID button is clicked', () => {
    const handleSelectCandidate = vi.fn()
    render(
      <EventTable
        events={mockEvents}
        onSelectCandidateId={handleSelectCandidate}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'cand-001' }))
    expect(handleSelectCandidate).toHaveBeenCalledWith('cand-001')
  })

  it('shows loading indicator when isLoading is true and events are empty', () => {
    render(
      <EventTable
        events={[]}
        isLoading={true}
      />
    )

    expect(screen.getByText(/Loading conjunction events…/i)).toBeInTheDocument()
  })
})
