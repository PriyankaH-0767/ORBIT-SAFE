import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Pagination } from '../components/results/Pagination'

describe('Pagination Component', () => {
  it('renders correct range and total count', () => {
    render(
      <Pagination
        total={50}
        limit={20}
        offset={0}
        onPageChange={vi.fn()}
        label="candidates"
      />
    )

    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
    expect(screen.getByText('50')).toBeInTheDocument()
  })

  it('disables previous button on first page and enables next button', () => {
    const handlePageChange = vi.fn()
    render(
      <Pagination
        total={50}
        limit={20}
        offset={0}
        onPageChange={handlePageChange}
      />
    )

    const prevBtn = screen.getByRole('button', { name: /Previous/i })
    const nextBtn = screen.getByRole('button', { name: /Next/i })

    expect(prevBtn).toBeDisabled()
    expect(nextBtn).toBeEnabled()

    fireEvent.click(nextBtn)
    expect(handlePageChange).toHaveBeenCalledWith(20)
  })

  it('disables next button on last page and enables previous button', () => {
    const handlePageChange = vi.fn()
    render(
      <Pagination
        total={50}
        limit={20}
        offset={40}
        onPageChange={handlePageChange}
      />
    )

    const prevBtn = screen.getByRole('button', { name: /Previous/i })
    const nextBtn = screen.getByRole('button', { name: /Next/i })

    expect(prevBtn).toBeEnabled()
    expect(nextBtn).toBeDisabled()

    fireEvent.click(prevBtn)
    expect(handlePageChange).toHaveBeenCalledWith(20)
  })

  it('renders nothing when total is 0', () => {
    const { container } = render(
      <Pagination
        total={0}
        limit={20}
        offset={0}
        onPageChange={vi.fn()}
      />
    )

    expect(container.firstChild).toBeNull()
  })
})
