import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { PlannerPage } from '../pages/PlannerPage'
import * as plansApi from '../api/plans'
import * as runsApi from '../api/runs'
import type { PlanRunAcceptedResponse } from '../types/plan'
import type { RunStatusResponse } from '../types/run'

describe('PlannerPage Integration Workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('submits plan, transitions to progress panel, and displays completed status', async () => {
    const acceptedResponse: PlanRunAcceptedResponse = {
      plan_id: 'plan-abc-123',
      run_id: 'run-xyz-789',
      status: 'queued',
      message: 'Screening run queued for execution',
      created_at: '2026-10-02T12:00:00Z',
    }

    const completedRun: RunStatusResponse = {
      run_id: 'run-xyz-789',
      plan_id: 'plan-abc-123',
      status: 'completed',
      progress_percent: 100.0,
      current_stage: 'completed',
      message: 'Run completed successfully',
      created_at: '2026-10-02T12:00:00Z',
      started_at: '2026-10-02T12:00:01Z',
      completed_at: '2026-10-02T12:00:04Z',
      error_message: null,
      candidate_count: 195,
      conjunction_event_count: 5,
      ranked_candidate_count: 195,
    }

    const createPlanSpy = vi.spyOn(plansApi, 'createPlan').mockResolvedValueOnce(acceptedResponse)
    const getRunSpy = vi.spyOn(runsApi, 'getRun').mockResolvedValue(completedRun)

    render(<PlannerPage />)

    // Form is displayed
    expect(screen.getByText(/Mission Planning & Screening Envelope/i)).toBeInTheDocument()

    // Click submit
    const submitBtn = screen.getByRole('button', { name: /Launch Screening Run/i })
    fireEvent.click(submitBtn)

    // Verify submission called
    await waitFor(() => {
      expect(createPlanSpy).toHaveBeenCalledTimes(1)
    })

    // UI transitioned to RunProgressPanel
    await waitFor(() => {
      expect(screen.getByText('run-xyz-789')).toBeInTheDocument()
      expect(screen.getByText('plan-abc-123')).toBeInTheDocument()
    })

    // Polling completes and displays summary counts
    await waitFor(() => {
      expect(screen.getByText('Screening Complete')).toBeInTheDocument()
      expect(screen.getAllByText('195')).toHaveLength(2)
      expect(screen.getByText('5')).toBeInTheDocument()
    })

    expect(getRunSpy).toHaveBeenCalled()
  })

  it('surfaces API submission error when backend rejects the request', async () => {
    vi.spyOn(plansApi, 'createPlan').mockRejectedValueOnce(
      new Error('Unable to connect to D-DATO backend at http://localhost:8000.')
    )

    render(<PlannerPage />)

    const submitBtn = screen.getByRole('button', { name: /Launch Screening Run/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText(/Unable to connect to D-DATO backend/i)).toBeInTheDocument()
    })

    // Form remains visible so user can retry
    expect(screen.getByText(/Mission Planning & Screening Envelope/i)).toBeInTheDocument()
  })
})
