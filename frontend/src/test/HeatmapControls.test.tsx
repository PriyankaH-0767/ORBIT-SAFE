import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { HeatmapControls } from '../components/results/HeatmapControls'
import type { HeatmapResponse } from '../types/heatmap'

const mockHeatmapData: HeatmapResponse = {
  run_id: 'run-test-01',
  status: 'completed',
  metric: 'risk_score',
  x_axis: 'delay_minutes',
  y_axis: 'altitude_km',
  inclination_values_deg: [97.0, 97.5, 98.0],
  layers: [
    {
      inclination_deg: 97.0,
      altitude_values_km: [500.0, 550.0],
      delay_values_minutes: [0.0, 30.0],
      values: [
        [10.5, 15.2],
        [null, 25.4],
      ],
      cells: [
        {
          candidate_id: 'cand-1',
          altitude_km: 500.0,
          inclination_deg: 97.0,
          delay_minutes: 0.0,
          risk_score: 10.5,
          rank: 1,
        },
      ],
    },
  ],
  total_candidates: 30,
  populated_cells: 18,
  min_risk_score: 4.2,
  max_risk_score: 48.7,
}

describe('HeatmapControls Component', () => {
  it('renders inclination selector with backend-provided options', () => {
    render(
      <HeatmapControls
        heatmapData={mockHeatmapData}
        selectedLayer={mockHeatmapData.layers[0]}
        selectedInclination={97.0}
        onSelectInclination={vi.fn()}
      />
    )

    const select = screen.getByRole('combobox', { name: /Inclination Slice/i })
    expect(select).toBeInTheDocument()

    expect(screen.getByRole('option', { name: '97.0°' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '97.5°' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '98.0°' })).toBeInTheDocument()
  })

  it('triggers onSelectInclination when inclination selection changes', () => {
    const handleSelect = vi.fn()
    render(
      <HeatmapControls
        heatmapData={mockHeatmapData}
        selectedLayer={mockHeatmapData.layers[0]}
        selectedInclination={97.0}
        onSelectInclination={handleSelect}
      />
    )

    const select = screen.getByRole('combobox', { name: /Inclination Slice/i })
    fireEvent.change(select, { target: { value: '97.5' } })

    expect(handleSelect).toHaveBeenCalledWith(97.5)
  })

  it('renders summary metrics correctly from backend response data', () => {
    render(
      <HeatmapControls
        heatmapData={mockHeatmapData}
        selectedLayer={mockHeatmapData.layers[0]}
        selectedInclination={97.0}
        onSelectInclination={vi.fn()}
      />
    )

    // Slice
    expect(screen.getByText('Selected Slice')).toBeInTheDocument()
    expect(screen.getAllByText('97.0°').length).toBeGreaterThan(0)

    // Populated Cells: layer has 1 cell, total populated is 18
    expect(screen.getByText('Populated Cells')).toBeInTheDocument()
    expect(screen.getByText('1 / 18')).toBeInTheDocument()

    // Total Candidates
    expect(screen.getByText('Total Candidates')).toBeInTheDocument()
    expect(screen.getByText('30')).toBeInTheDocument()

    // Min & Max Risk
    expect(screen.getByText('Min Risk (Run)')).toBeInTheDocument()
    expect(screen.getByText('4.2')).toBeInTheDocument()
    expect(screen.getByText('Max Risk (Run)')).toBeInTheDocument()
    expect(screen.getByText('48.7')).toBeInTheDocument()
  })

  it('disables the dropdown when isLoading is true', () => {
    render(
      <HeatmapControls
        heatmapData={mockHeatmapData}
        selectedLayer={mockHeatmapData.layers[0]}
        selectedInclination={97.0}
        onSelectInclination={vi.fn()}
        isLoading={true}
      />
    )

    const select = screen.getByRole('combobox', { name: /Inclination Slice/i })
    expect(select).toBeDisabled()
  })
})
