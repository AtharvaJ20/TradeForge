import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StreaksCard } from '../StreaksCard'
import { STREAKS_FIXTURE, STREAKS_EMPTY_FIXTURE } from '@/__tests__/msw/handlers'
import type { useStreaks } from '../../hooks/useStreaks'

vi.mock('../../hooks/useStreaks', () => ({
  useStreaks: vi.fn(),
}))

import { useStreaks as _useStreaks } from '../../hooks/useStreaks'

const mockUseStreaks = vi.mocked(_useStreaks)

function withData(data: typeof STREAKS_FIXTURE) {
  mockUseStreaks.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useStreaks>)
}

describe('StreaksCard', () => {
  it('renders section landmark with heading', () => {
    withData(STREAKS_FIXTURE)
    render(<StreaksCard />)
    expect(screen.getByRole('region', { name: /consecutive streaks/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /streaks/i })).toBeInTheDocument()
  })

  it('renders current loss streak with negative sign from fixture (W W B L L pattern)', () => {
    withData(STREAKS_FIXTURE)
    render(<StreaksCard />)
    // current_loss_streak = 2 → displayed as -2
    expect(screen.getByText('-2')).toBeInTheDocument()
  })

  it('renders max win and max loss streak stat labels', () => {
    withData(STREAKS_FIXTURE)
    render(<StreaksCard />)
    expect(screen.getByText(/max win streak/i)).toBeInTheDocument()
    expect(screen.getByText(/max loss streak/i)).toBeInTheDocument()
    // Both max streaks are 2 in the fixture — confirm via label presence
    expect(screen.getByText(/avg win run/i)).toBeInTheDocument()
    expect(screen.getByText(/avg loss run/i)).toBeInTheDocument()
  })

  it('shows "No closed trades yet" when all streak values are 0', () => {
    withData(STREAKS_EMPTY_FIXTURE)
    render(<StreaksCard />)
    expect(screen.getByText(/no closed trades yet/i)).toBeInTheDocument()
  })

  it('shows a loading skeleton while data is loading', () => {
    mockUseStreaks.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useStreaks>)
    render(<StreaksCard />)
    expect(screen.getByRole('status', { name: /loading streaks/i })).toBeInTheDocument()
  })

  it('shows error message on fetch failure', () => {
    mockUseStreaks.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useStreaks>)
    render(<StreaksCard />)
    expect(screen.getByText(/failed to load streaks/i)).toBeInTheDocument()
  })

  it('shows a positive current streak with + prefix when winning', () => {
    withData({
      ...STREAKS_FIXTURE,
      current_win_streak: 3,
      current_loss_streak: 0,
    })
    render(<StreaksCard />)
    expect(screen.getByText('+3')).toBeInTheDocument()
  })
})
