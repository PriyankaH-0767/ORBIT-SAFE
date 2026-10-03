import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getRunGlobe, DEFAULT_GLOBE_OPTIONS } from '../api/globe'

describe('getRunGlobe API client', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('forms the correct default URL with bounded parameters', async () => {
    const mockResponse = {
      run_id: 'test-run-123',
      status: 'completed',
      frame: 'TEME',
      time_scale: 'UTC',
      sample_step_seconds: 300,
      epoch_start: '2026-10-15T12:00:00Z',
      epoch_end: '2026-10-18T12:00:00Z',
      candidate_count: 0,
      debris_count: 0,
      event_count: 0,
      candidates: [],
      debris: [],
      events: [],
    }

    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    const result = await getRunGlobe('test-run-123', DEFAULT_GLOBE_OPTIONS)

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    const calledUrl = vi.mocked(globalThis.fetch).mock.calls[0][0] as string

    expect(calledUrl).toContain('/api/v1/runs/test-run-123/globe')
    expect(calledUrl).toContain('sample_step_seconds=300')
    expect(calledUrl).toContain('max_candidates=5')
    expect(calledUrl).toContain('max_debris=10')
    expect(result.frame).toBe('TEME')
    expect(result.time_scale).toBe('UTC')
  })

  it('formats candidate_ids as comma-separated string and excludes empty ids', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: 'run-456' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    await getRunGlobe('run-456', {
      candidate_ids: ['cand-1', '  ', 'cand-2'],
      sample_step_seconds: 60,
    })

    const calledUrl = vi.mocked(globalThis.fetch).mock.calls[0][0] as string
    expect(calledUrl).toContain('candidate_ids=cand-1%2Ccand-2')
    expect(calledUrl).toContain('sample_step_seconds=60')
    // Ensure no trailing comma or whitespace
    expect(calledUrl).not.toContain('%20')
  })

  it('omits candidate_ids query param entirely when empty array is passed', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: 'run-789' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    await getRunGlobe('run-789', {
      candidate_ids: [],
      sample_step_seconds: 600,
    })

    const calledUrl = vi.mocked(globalThis.fetch).mock.calls[0][0] as string
    expect(calledUrl).not.toContain('candidate_ids')
    expect(calledUrl).toContain('sample_step_seconds=600')
  })
})
