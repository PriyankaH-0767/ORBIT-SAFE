import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { RunProgressPanel } from '../components/run/RunProgressPanel'
import type { RunStatusResponse } from '../types/run'

describe('RunProgressPanel Component', () => {
  it('renders queued state correctly', () => {
    const run: RunStatusResponse = {
      run_id: 'run-1234',
      plan_id: 'plan-5678',
      status: 'queued',
      progress_percent: 0.0,
      current_stage: 'queued',
      message: 'Screening run queued for execution',
      created_at: '2026-10-02T12:00:00Z',
      started_at: null,
      completed_at: null,
      error_message: null,
      candidate_count: 0,
      conjunction_event_count: 0,
      ranked_candidate_count: 0,
    }

    render(<RunProgressPanel run={run} runId="run-1234" planId="plan-5678" onReset={vi.fn()} />)

    expect(screen.getByText('QUEUED')).toBeInTheDocument()
    expect(screen.getByText('run-1234')).toBeInTheDocument()
    expect(screen.getByText('plan-5678')).toBeInTheDocument()
    expect(screen.getByText(/Screening run queued for execution/i)).toBeInTheDocument()
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('renders running state with human-mapped stage label and progress', () => {
    const run: RunStatusResponse = {
      run_id: 'run-1234',
      plan_id: 'plan-5678',
      status: 'running',
      progress_percent: 65.0,
      current_stage: 'conjunction_screening',
      message: 'Screening close approaches against catalog',
      created_at: '2026-10-02T12:00:00Z',
      started_at: '2026-10-02T12:00:01Z',
      completed_at: null,
      error_message: null,
      candidate_count: 30,
      conjunction_event_count: 2,
      ranked_candidate_count: 0,
    }

    render(<RunProgressPanel run={run} runId="run-1234" planId="plan-5678" onReset={vi.fn()} />)

    expect(screen.getByText('RUNNING')).toBeInTheDocument()
    expect(screen.getByText('Screening close approaches')).toBeInTheDocument()
    expect(screen.getByText('65%')).toBeInTheDocument()
    expect(screen.getByText(/Screening close approaches against catalog/i)).toBeInTheDocument()
  })

  it('renders completed state with candidate counts and conjunction event count', () => {
    const run: RunStatusResponse = {
      run_id: 'run-1234',
      plan_id: 'plan-5678',
      status: 'completed',
      progress_percent: 100.0,
      current_stage: 'completed',
      message: 'Run completed successfully',
      created_at: '2026-10-02T12:00:00Z',
      started_at: '2026-10-02T12:00:01Z',
      completed_at: '2026-10-02T12:00:05Z',
      error_message: null,
      candidate_count: 195,
      conjunction_event_count: 14,
      ranked_candidate_count: 195,
    }

    const handleViewResults = vi.fn()
    render(
      <RunProgressPanel
        run={run}
        runId="run-1234"
        planId="plan-5678"
        onReset={vi.fn()}
        onViewResults={handleViewResults}
      />
    )

    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText('Screening Complete')).toBeInTheDocument()
    expect(screen.getAllByText('195')).toHaveLength(2)
    expect(screen.getByText('14')).toBeInTheDocument()

    // View Results button
    const viewResultsBtn = screen.getByRole('button', { name: /View Results/i })
    expect(viewResultsBtn).toBeInTheDocument()

    fireEvent.click(viewResultsBtn)
    expect(handleViewResults).toHaveBeenCalledWith('run-1234')
  })

  it('renders failed state with error message and retry action', () => {
    const handleReset = vi.fn()
    const run: RunStatusResponse = {
      run_id: 'run-1234',
      plan_id: 'plan-5678',
      status: 'failed',
      progress_percent: 35.0,
      current_stage: 'conjunction_screening',
      message: 'Execution aborted',
      created_at: '2026-10-02T12:00:00Z',
      started_at: '2026-10-02T12:00:01Z',
      completed_at: '2026-10-02T12:00:03Z',
      error_message: 'Ephemeris propagation failure in orbit integration',
      candidate_count: 10,
      conjunction_event_count: 0,
      ranked_candidate_count: 0,
    }

    render(<RunProgressPanel run={run} runId="run-1234" planId="plan-5678" onReset={handleReset} />)

    expect(screen.getByText('FAILED')).toBeInTheDocument()
    expect(screen.getByText('Screening Execution Failed')).toBeInTheDocument()
    expect(screen.getByText(/Ephemeris propagation failure in orbit integration/i)).toBeInTheDocument()

    const retryBtn = screen.getByRole('button', { name: /Modify Parameters & Retry/i })
    fireEvent.click(retryBtn)
    expect(handleReset).toHaveBeenCalledTimes(1)
  })
})
