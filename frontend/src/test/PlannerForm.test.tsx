import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PlannerForm } from '../components/planner/PlannerForm'
import { DEFAULT_PLAN_FORM } from '../types/plan'

describe('PlannerForm Component', () => {
  it('renders all sections and default form fields', () => {
    const handleSubmit = vi.fn()
    render(<PlannerForm onSubmit={handleSubmit} />)

    // Form sections
    expect(screen.getByText(/Section A: Candidate Search Space/i)).toBeInTheDocument()
    expect(screen.getByText(/Section B: Orbit Setup & Perturbations/i)).toBeInTheDocument()
    expect(screen.getByText(/Section C: Screening Time Horizon/i)).toBeInTheDocument()
    expect(screen.getByText(/Section D: Reference Orbit & Propulsion Budget/i)).toBeInTheDocument()
    expect(screen.getByText(/Section E: Multi-Objective Ranking Weights/i)).toBeInTheDocument()
    expect(screen.getByText(/Section F: Catalog Data Source & Execution Mode/i)).toBeInTheDocument()

    // Default values
    expect(screen.getByLabelText(/Min Altitude/i)).toHaveValue(DEFAULT_PLAN_FORM.altitude_min_km)
    expect(screen.getByLabelText(/Max Altitude/i)).toHaveValue(DEFAULT_PLAN_FORM.altitude_max_km)
    expect(screen.getByLabelText(/Min Inclination/i)).toHaveValue(DEFAULT_PLAN_FORM.inclination_min_deg)
    expect(screen.getByLabelText(/Max Inclination/i)).toHaveValue(DEFAULT_PLAN_FORM.inclination_max_deg)
    expect(screen.getByLabelText(/Fuel Consumption Weight/i)).toHaveValue(DEFAULT_PLAN_FORM.fuel_weight)
    expect(screen.getByLabelText(/Debris Screening Risk Weight/i)).toHaveValue(DEFAULT_PLAN_FORM.risk_weight)
    expect(screen.getByLabelText(/Offline Demo Mode/i)).toBeChecked()

    // Submit button is active with defaults
    const submitBtn = screen.getByRole('button', { name: /Launch Screening Run/i })
    expect(submitBtn).not.toBeDisabled()
  })

  it('displays inline validation errors when min exceeds max', () => {
    const handleSubmit = vi.fn()
    render(<PlannerForm onSubmit={handleSubmit} />)

    const minAltInput = screen.getByLabelText(/Min Altitude/i)
    fireEvent.change(minAltInput, { target: { value: '700' } }) // 700 > 600 max

    expect(screen.getByText(/Min altitude cannot exceed max altitude/i)).toBeInTheDocument()

    // Submit button should be disabled
    const submitBtn = screen.getByRole('button', { name: /Launch Screening Run/i })
    expect(submitBtn).toBeDisabled()
  })

  it('displays validation error when weights do not sum to 1.0', () => {
    const handleSubmit = vi.fn()
    render(<PlannerForm onSubmit={handleSubmit} />)

    const fuelWeightInput = screen.getByLabelText(/Fuel Consumption Weight/i)
    fireEvent.change(fuelWeightInput, { target: { value: '0.8' } }) // 0.8 + 0.6 = 1.4

    expect(screen.getByRole('alert')).toHaveTextContent(/must sum to 1.0/i)
    const submitBtn = screen.getByRole('button', { name: /Launch Screening Run/i })
    expect(submitBtn).toBeDisabled()
  })

  it('disables submit when candidate grid produces > 300 candidates', () => {
    const handleSubmit = vi.fn()
    render(<PlannerForm onSubmit={handleSubmit} />)

    // Set altitude step to 1 km -> (600 - 500) / 1 + 1 = 101 altitudes
    // 101 * 3 * 13 = 3939 candidates > 300
    const altStepInput = screen.getByLabelText(/Altitude Step/i)
    fireEvent.change(altStepInput, { target: { value: '1' } })

    expect(screen.getByText(/exceeding the backend maximum limit of 300/i)).toBeInTheDocument()
    const submitBtn = screen.getByRole('button', { name: /Launch Screening Run/i })
    expect(submitBtn).toBeDisabled()
  })

  it('calls onSubmit with form values when valid form is submitted', async () => {
    const handleSubmit = vi.fn().mockResolvedValue(undefined)
    render(<PlannerForm onSubmit={handleSubmit} />)

    const submitBtn = screen.getByRole('button', { name: /Launch Screening Run/i })
    expect(submitBtn).not.toBeDisabled()

    fireEvent.click(submitBtn)

    expect(handleSubmit).toHaveBeenCalledTimes(1)
    const submittedPayload = handleSubmit.mock.calls[0][0]
    expect(submittedPayload.altitude_min_km).toBe(500)
    expect(submittedPayload.altitude_max_km).toBe(600)
    expect(submittedPayload.demo_mode).toBe(true)
  })
})
