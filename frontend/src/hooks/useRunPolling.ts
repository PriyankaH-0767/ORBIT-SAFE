import { useState, useEffect, useCallback } from 'react'
import { getRun } from '../api/runs'
import type { RunStatusResponse } from '../types/run'

export interface UseRunPollingReturn {
  run: RunStatusResponse | null
  status: string | null
  progressPercent: number
  currentStage: string | null
  message: string | null
  candidateCount: number
  conjunctionEventCount: number
  rankedCandidateCount: number
  errorMessage: string | null
  isLoading: boolean
  networkError: string | null
  refetch: () => Promise<void>
}

/**
 * Custom React hook for polling screening run status until a terminal state is reached.
 */
export function useRunPolling(
  runId: string | null,
  pollIntervalMs = 1200
): UseRunPollingReturn {
  const [run, setRun] = useState<RunStatusResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(Boolean(runId))
  const [networkError, setNetworkError] = useState<string | null>(null)

  const manualRefetch = useCallback(async () => {
    if (!runId) return
    try {
      setIsLoading(true)
      const data = await getRun(runId)
      setRun(data)
      setNetworkError(null)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to poll run status'
      setNetworkError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [runId])

  useEffect(() => {
    if (!runId) return

    let isCancelled = false
    let timerId: number | null = null

    async function poll() {
      try {
        const data = await getRun(runId!)
        if (isCancelled) return

        setRun(data)
        setNetworkError(null)
        setIsLoading(false)

        const isTerminal = ['completed', 'failed', 'cancelled'].includes(data.status.toLowerCase())
        if (!isTerminal && !isCancelled) {
          timerId = window.setTimeout(() => {
            void poll()
          }, pollIntervalMs)
        }
      } catch (err) {
        if (isCancelled) return
        const msg = err instanceof Error ? err.message : 'Failed to poll run status'
        setNetworkError(msg)
        setIsLoading(false)
        timerId = window.setTimeout(() => {
          void poll()
        }, pollIntervalMs * 1.5)
      }
    }

    void poll()

    return () => {
      isCancelled = true
      if (timerId !== null) {
        window.clearTimeout(timerId)
      }
    }
  }, [runId, pollIntervalMs])

  const currentRun = runId ? run : null

  return {
    run: currentRun,
    status: currentRun?.status ?? null,
    progressPercent: currentRun?.progress_percent ?? 0,
    currentStage: currentRun?.current_stage ?? null,
    message: currentRun?.message ?? null,
    candidateCount: currentRun?.candidate_count ?? 0,
    conjunctionEventCount: currentRun?.conjunction_event_count ?? 0,
    rankedCandidateCount: currentRun?.ranked_candidate_count ?? 0,
    errorMessage: currentRun?.error_message ?? null,
    isLoading: runId ? isLoading : false,
    networkError: runId ? networkError : null,
    refetch: manualRefetch,
  }
}
