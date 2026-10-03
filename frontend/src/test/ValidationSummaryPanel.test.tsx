import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ValidationSummaryPanel } from '../components/results/ValidationSummaryPanel'
import type { ValidationSummary } from '../types/validation'

describe('ValidationSummaryPanel Component (Phase P23)', () => {
  const mockPopulatedSummary: ValidationSummary = {
    d_dato_event_count: 8,
    external_event_count: 10,
    matched_event_count: 7,
    d_dato_only_count: 1,
    external_only_count: 3,
    external_coverage_percent: 70.0,
    d_dato_match_rate_percent: 87.5,
    mean_abs_tca_error_seconds: 14.2,
    max_abs_tca_error_seconds: 28.5,
    mean_abs_miss_distance_difference_km: 0.125,
    max_abs_miss_distance_difference_km: 0.45,
  }

  it('1. renders all 5 event count cards and descriptive comparison metrics', () => {
    render(<ValidationSummaryPanel summary={mockPopulatedSummary} />)

    // Event count cards
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()

    // Descriptive metrics
    expect(screen.getByText('70.0%')).toBeInTheDocument()
    expect(screen.getByText('87.5%')).toBeInTheDocument()
    expect(screen.getByText('14.2 s')).toBeInTheDocument()
    expect(screen.getByText('28.5 s')).toBeInTheDocument()
    expect(screen.getByText('0.125 km')).toBeInTheDocument()
    expect(screen.getByText('0.450 km')).toBeInTheDocument()
  })

  it('2. renders "N/A" for null metrics instead of replacing with 0', () => {
    const mockEmptySummary: ValidationSummary = {
      d_dato_event_count: 0,
      external_event_count: 0,
      matched_event_count: 0,
      d_dato_only_count: 0,
      external_only_count: 0,
      external_coverage_percent: null,
      d_dato_match_rate_percent: null,
      mean_abs_tca_error_seconds: null,
      max_abs_tca_error_seconds: null,
      mean_abs_miss_distance_difference_km: null,
      max_abs_miss_distance_difference_km: null,
    }

    render(<ValidationSummaryPanel summary={mockEmptySummary} />)

    // All descriptive metrics should be N/A
    const naElements = screen.getAllByText('N/A')
    expect(naElements.length).toBe(6)

    // Verify 0 is not rendered in metric values
    expect(screen.queryByText('0.0%')).not.toBeInTheDocument()
    expect(screen.queryByText('0.0 s')).not.toBeInTheDocument()
    expect(screen.queryByText('0.000 km')).not.toBeInTheDocument()
  })
})
