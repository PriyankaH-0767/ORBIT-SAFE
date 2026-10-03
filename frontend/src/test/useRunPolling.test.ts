import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useRunPolling } from '../hooks/useRunPolling'
import * as runsApi from '../api/runs'
import type { RunStatusResponse } from '../types/run'

describe('useRunPolling hook', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('does not poll when runId is null', () => {
    const getRunSpy = vi.spyOn(runsApi, 'getRun')
    const { result } = renderHook(() => useRunPolling(null))

    expect(result.current.run).toBeNull()
    expect(result.current.status).toBeNull()
    expect(result.current.isLoading).toBe(false)
    expect(getRunSpy).not.toHaveBeenCalled()
  })

  it('polls running state and stops after reaching completed terminal state', async () => {
    const runningRun: RunStatusResponse = {
      run_id: 'test-run-1',
      plan_id: 'test-plan-1',
      status: 'running',
      progress_percent: 50.0,
      current_stage: 'fuel',
      message: 'Calculating fuel',
      created_at: '2026-10-02T12:00:00Z',
      started_at: '2026-10-02T12:00:01Z',
      completed_at: null,
      error_message: null,
      candidate_count: 20,
      conjunction_event_count: 0,
      ranked_candidate_count: 0,
    }

    const completedRun: RunStatusResponse = {
      ...runningRun,
      status: 'completed',
      progress_percent: 100.0,
      current_stage: 'completed',
      message: 'Screening finished',
      completed_at: '2026-10-02T12:00:03Z',
      ranked_candidate_count: 20,
    }

    const getRunSpy = vi
      .spyOn(runsApi, 'getRun')
      .mockResolvedValueOnce(runningRun)
      .mockResolvedValueOnce(completedRun)

    const { result } = renderHook(() => useRunPolling('test-run-1', 50))

    // Polls until terminal completed state is reached
    await waitFor(() => {
      expect(result.current.status).toBe('completed')
      expect(result.current.progressPercent).toBe(100.0)
    })
    expect(getRunSpy).toHaveBeenCalledTimes(2)

    // Wait and confirm no additional calls occur (terminal state stopped polling)
    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(getRunSpy).toHaveBeenCalledTimes(2)
  })

  it('stops polling when run reaches failed terminal state', async () => {
    const failedRun: RunStatusResponse = {
      run_id: 'test-run-fail',
      plan_id: 'test-plan-1',
      status: 'failed',
      progress_percent: 20.0,
      current_stage: 'ingestion',
      message: 'Failed to ingest',
      created_at: '2026-10-02T12:00:00Z',
      started_at: '2026-10-02T12:00:01Z',
      completed_at: '2026-10-02T12:00:02Z',
      error_message: 'Invalid catalog data',
      candidate_count: 0,
      conjunction_event_count: 0,
      ranked_candidate_count: 0,
    }

    const getRunSpy = vi.spyOn(runsApi, 'getRun').mockResolvedValueOnce(failedRun)

    const { result } = renderHook(() => useRunPolling('test-run-fail', 50))

    await waitFor(() => {
      expect(result.current.status).toBe('failed')
      expect(result.current.errorMessage).toBe('Invalid catalog data')
    })
    expect(getRunSpy).toHaveBeenCalledTimes(1)

    // Wait and confirm no additional calls occur
    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(getRunSpy).toHaveBeenCalledTimes(1)
  })
})
