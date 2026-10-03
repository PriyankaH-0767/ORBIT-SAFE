import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  createValidation,
  getRunValidation,
  getValidation,
  DEFAULT_VALIDATION_REQUEST,
} from '../api/validation'

describe('Validation API client (Phase P23)', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('1. createValidation sends POST to /api/v1/runs/{run_id}/validation with default body', async () => {
    const mockResponse = {
      validation_id: 'val-123',
      run_id: 'run-999',
      status: 'completed',
      source: 'socrates_demo_fixture',
      validation_created_at: '2026-10-15T12:05:00Z',
      summary: {
        d_dato_event_count: 5,
        external_event_count: 6,
        matched_event_count: 4,
        d_dato_only_count: 1,
        external_only_count: 2,
      },
      matches: [],
      d_dato_only: [],
      external_only: [],
      notes: [],
    }

    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    const result = await createValidation('run-999')

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    const [calledUrl, calledOptions] = vi.mocked(globalThis.fetch).mock.calls[0] as [string, RequestInit]

    expect(calledUrl).toContain('/api/v1/runs/run-999/validation')
    expect(calledOptions.method).toBe('POST')

    const parsedBody = JSON.parse(calledOptions.body as string)
    expect(parsedBody.source).toBe(DEFAULT_VALIDATION_REQUEST.source)
    expect(parsedBody.tca_tolerance_seconds).toBe(300.0)
    expect(parsedBody.miss_distance_tolerance_km).toBe(5.0)
    expect(parsedBody.demo_mode).toBe(true)

    expect(result.validation_id).toBe('val-123')
    expect(result.source).toBe('socrates_demo_fixture')
  })

  it('2. createValidation supports custom tolerance overrides', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ validation_id: 'val-custom' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    await createValidation('run-custom', {
      source: 'socrates',
      tca_tolerance_seconds: 120.0,
      miss_distance_tolerance_km: 2.5,
      demo_mode: false,
    })

    const [, calledOptions] = vi.mocked(globalThis.fetch).mock.calls[0] as [string, RequestInit]
    const parsedBody = JSON.parse(calledOptions.body as string)
    expect(parsedBody.tca_tolerance_seconds).toBe(120.0)
    expect(parsedBody.miss_distance_tolerance_km).toBe(2.5)
    expect(parsedBody.demo_mode).toBe(false)
  })

  it('3. getRunValidation sends GET to /api/v1/runs/{run_id}/validation', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ validation_id: 'val-latest', run_id: 'run-777' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    const result = await getRunValidation('run-777')

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    const [calledUrl, calledOptions] = vi.mocked(globalThis.fetch).mock.calls[0] as [string, RequestInit]
    expect(calledUrl).toContain('/api/v1/runs/run-777/validation')
    expect(calledOptions.method).toBe('GET')
    expect(result.validation_id).toBe('val-latest')
  })

  it('4. getValidation sends GET to /api/v1/validations/{validation_id}', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ validation_id: 'val-exact' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    const result = await getValidation('val-exact')

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    const [calledUrl, calledOptions] = vi.mocked(globalThis.fetch).mock.calls[0] as [string, RequestInit]
    expect(calledUrl).toContain('/api/v1/validations/val-exact')
    expect(calledOptions.method).toBe('GET')
    expect(result.validation_id).toBe('val-exact')
  })
})
