import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ValidationProvenance } from '../components/results/ValidationProvenance'

describe('ValidationProvenance Component (Phase P23)', () => {
  it('1. renders synthetic demo reference data badge and details', () => {
    render(
      <ValidationProvenance
        source="socrates_demo_fixture"
        status="completed"
        sourceFetchedAt="2026-10-15T12:00:00Z"
        validationCreatedAt="2026-10-15T12:05:00Z"
        validationId="val-demo-999-abc"
      />
    )

    expect(screen.getByText(/synthetic demo reference data/i)).toBeInTheDocument()
    expect(screen.getByText('completed')).toBeInTheDocument()
    expect(screen.getByText('socrates_demo_fixture')).toBeInTheDocument()
    expect(screen.getByText(/ID: val-demo/i)).toBeInTheDocument()
  })

  it('2. renders cached external reference data badge', () => {
    render(
      <ValidationProvenance
        source="socrates_cache"
        status="completed"
        sourceFetchedAt="2026-10-15T08:00:00Z"
        validationCreatedAt="2026-10-15T08:02:00Z"
        validationId="val-cache-123"
      />
    )

    expect(screen.getByText(/cached external reference data/i)).toBeInTheDocument()
    expect(screen.getByText('socrates_cache')).toBeInTheDocument()
  })

  it('3. renders live external reference data badge', () => {
    render(
      <ValidationProvenance
        source="socrates_live"
        status="completed"
        sourceFetchedAt={null}
        validationCreatedAt="2026-10-15T09:00:00Z"
        validationId="val-live-456"
      />
    )

    expect(screen.getByText(/live external reference data/i)).toBeInTheDocument()
    expect(screen.getByText('socrates_live')).toBeInTheDocument()
  })
})
