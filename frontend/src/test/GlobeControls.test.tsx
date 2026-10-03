import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { GlobeControls } from '../components/results/GlobeControls'

describe('GlobeControls Component', () => {
  const defaultProps = {
    candidateCount: 3,
    totalCandidates: 15,
    showDebris: true,
    onToggleDebris: vi.fn(),
    maxDebris: 10,
    onChangeMaxDebris: vi.fn(),
    sampleStep: 300,
    onChangeSampleStep: vi.fn(),
    isPlaying: false,
    onTogglePlay: vi.fn(),
    currentUtcTime: '2026-10-15T12:00:00Z',
    playbackSpeed: 1,
    onChangeSpeed: vi.fn(),
    onResetView: vi.fn(),
    onFocusSelected: vi.fn(),
    hasSelection: true,
    disabled: false,
  }

  it('renders candidates badge and current UTC clock timestamp', () => {
    render(<GlobeControls {...defaultProps} />)

    expect(screen.getByText('3 shown')).toBeInTheDocument()
    expect(screen.getByText('of 15')).toBeInTheDocument()
    expect(screen.getByText('2026-10-15T12:00:00Z')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /play orbital animation/i })).toBeInTheDocument()
  })

  it('handles play/pause toggle clicking', async () => {
    const user = userEvent.setup()
    const onTogglePlay = vi.fn()
    render(<GlobeControls {...defaultProps} onTogglePlay={onTogglePlay} />)

    const playBtn = screen.getByRole('button', { name: /play orbital animation/i })
    await user.click(playBtn)
    expect(onTogglePlay).toHaveBeenCalledTimes(1)
  })

  it('allows switching playback speed', async () => {
    const user = userEvent.setup()
    const onChangeSpeed = vi.fn()
    render(<GlobeControls {...defaultProps} onChangeSpeed={onChangeSpeed} />)

    const speed60Btn = screen.getByRole('button', { name: '60x' })
    await user.click(speed60Btn)
    expect(onChangeSpeed).toHaveBeenCalledWith(60)
  })

  it('toggles debris inclusion and handles debris limit selection', async () => {
    const user = userEvent.setup()
    const onToggleDebris = vi.fn()
    const onChangeMaxDebris = vi.fn()

    render(
      <GlobeControls
        {...defaultProps}
        onToggleDebris={onToggleDebris}
        onChangeMaxDebris={onChangeMaxDebris}
      />
    )

    const debrisCheckbox = screen.getByLabelText(/show debris/i)
    await user.click(debrisCheckbox)
    expect(onToggleDebris).toHaveBeenCalledWith(false)

    const debrisLimitSelect = screen.getByLabelText(/debris limit:/i)
    await user.selectOptions(debrisLimitSelect, '25')
    expect(onChangeMaxDebris).toHaveBeenCalledWith(25)
  })

  it('handles sampling step selection', async () => {
    const user = userEvent.setup()
    const onChangeSampleStep = vi.fn()

    render(<GlobeControls {...defaultProps} onChangeSampleStep={onChangeSampleStep} />)

    const sampleSelect = screen.getByLabelText(/sampling:/i)
    await user.selectOptions(sampleSelect, '60')
    expect(onChangeSampleStep).toHaveBeenCalledWith(60)
  })

  it('triggers camera reset and focus callbacks', async () => {
    const user = userEvent.setup()
    const onResetView = vi.fn()
    const onFocusSelected = vi.fn()

    render(
      <GlobeControls
        {...defaultProps}
        onResetView={onResetView}
        onFocusSelected={onFocusSelected}
      />
    )

    const resetBtn = screen.getByRole('button', { name: /reset view/i })
    await user.click(resetBtn)
    expect(onResetView).toHaveBeenCalledTimes(1)

    const focusBtn = screen.getByRole('button', { name: /focus selected/i })
    await user.click(focusBtn)
    expect(onFocusSelected).toHaveBeenCalledTimes(1)
  })
})
