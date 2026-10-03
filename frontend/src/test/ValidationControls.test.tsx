import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ValidationControls } from '../components/results/ValidationControls'

describe('ValidationControls Component (Phase P23)', () => {
  const mockOnRunValidation = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('1. renders default controls and inputs properly', () => {
    render(
      <ValidationControls
        onRunValidation={mockOnRunValidation}
        isRunning={false}
      />
    )

    expect(screen.getByText(/external reference comparison configuration/i)).toBeInTheDocument()
    expect(screen.getByText(/SOCRATES \(CelesTrak\)/i)).toBeInTheDocument()
    expect(screen.getByText(/validation compares d-dato screening events/i)).toBeInTheDocument()

    const tcaInput = screen.getByLabelText(/tca tolerance/i) as HTMLInputElement
    expect(tcaInput.value).toBe('300')

    const missInput = screen.getByLabelText(/miss-distance tolerance/i) as HTMLInputElement
    expect(missInput.value).toBe('5')

    const demoCheckbox = screen.getByRole('checkbox') as HTMLInputElement
    expect(demoCheckbox.checked).toBe(true)

    expect(screen.getByRole('button', { name: /run external validation/i })).toBeEnabled()
  })

  it('2. submits configuration and calls onRunValidation with payload', () => {
    render(
      <ValidationControls
        onRunValidation={mockOnRunValidation}
        isRunning={false}
      />
    )

    const tcaInput = screen.getByLabelText(/tca tolerance/i)
    const missInput = screen.getByLabelText(/miss-distance tolerance/i)

    fireEvent.change(tcaInput, { target: { value: '180' } })
    fireEvent.change(missInput, { target: { value: '3.5' } })

    const submitBtn = screen.getByRole('button', { name: /run external validation/i })
    fireEvent.click(submitBtn)

    expect(mockOnRunValidation).toHaveBeenCalledTimes(1)
    expect(mockOnRunValidation).toHaveBeenCalledWith({
      source: 'socrates',
      tca_tolerance_seconds: 180,
      miss_distance_tolerance_km: 3.5,
      demo_mode: true,
    })
  })

  it('3. displays loading indicator and disables submit button when isRunning is true', () => {
    render(
      <ValidationControls
        onRunValidation={mockOnRunValidation}
        isRunning={true}
      />
    )

    expect(screen.getByText(/validating screening results…/i)).toBeInTheDocument()
    const submitBtn = screen.getByRole('button')
    expect(submitBtn).toBeDisabled()

    // Form inputs should be disabled
    expect(screen.getByLabelText(/tca tolerance/i)).toBeDisabled()
    expect(screen.getByLabelText(/miss-distance tolerance/i)).toBeDisabled()
    expect(screen.getByRole('checkbox')).toBeDisabled()

    // Clicking should not trigger onRunValidation
    fireEvent.click(submitBtn)
    expect(mockOnRunValidation).not.toHaveBeenCalled()
  })

  it('4. blocks submission and displays error when tolerance values are invalid (<= 0)', () => {
    render(
      <ValidationControls
        onRunValidation={mockOnRunValidation}
        isRunning={false}
      />
    )

    const tcaInput = screen.getByLabelText(/tca tolerance/i)
    fireEvent.change(tcaInput, { target: { value: '-10' } })

    const submitBtn = screen.getByRole('button', { name: /run external validation/i })
    fireEvent.click(submitBtn)

    expect(screen.getByText(/tca tolerance must be a positive number/i)).toBeInTheDocument()
    expect(mockOnRunValidation).not.toHaveBeenCalled()
  })
})
