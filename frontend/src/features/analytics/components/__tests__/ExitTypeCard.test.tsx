import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { ExitTypeCard } from '../ExitTypeCard'
import {
  EXIT_TYPES_FIXTURE,
  EXIT_TYPES_HIGH_UNTAGGED_FIXTURE,
} from '@/__tests__/msw/handlers'
import type { useExitTypes } from '../../hooks/useExitTypes'

vi.mock('../../hooks/useExitTypes', () => ({
  useExitTypes: vi.fn(),
}))

import { useExitTypes as _useExitTypes } from '../../hooks/useExitTypes'

const mockUseExitTypes = vi.mocked(_useExitTypes)

function withData(data: typeof EXIT_TYPES_FIXTURE) {
  mockUseExitTypes.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useExitTypes>)
}

describe('ExitTypeCard', () => {
  it('renders section landmark and heading', () => {
    withData(EXIT_TYPES_FIXTURE)
    render(<ExitTypeCard />)
    expect(screen.getByRole('region', { name: /exit type analysis/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /exit type/i })).toBeInTheDocument()
  })

  it('renders a row for each exit type in the fixture', () => {
    withData(EXIT_TYPES_FIXTURE)
    render(<ExitTypeCard />)
    const table = screen.getByRole('table')
    const rows = within(table).getAllByRole('row')
    // 1 header + 4 data rows (TARGET_HIT, STOP_HIT, DISCRETIONARY, Untagged)
    expect(rows.length).toBe(5)
  })

  it('labels the NULL exit_type row as "Untagged"', () => {
    withData(EXIT_TYPES_FIXTURE)
    render(<ExitTypeCard />)
    expect(screen.getByText('Untagged')).toBeInTheDocument()
  })

  it('does NOT show the data quality alert when untagged pct ≤ 20%', () => {
    // Fixture: 3 untagged out of 30 total = 10% — below threshold
    withData(EXIT_TYPES_FIXTURE)
    render(<ExitTypeCard />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows role="alert" callout when untagged pct > 20% (AC-12.5-05)', () => {
    // HIGH_UNTAGGED: 7 untagged out of 10 total = 70%
    withData(EXIT_TYPES_HIGH_UNTAGGED_FIXTURE)
    render(<ExitTypeCard />)
    const alert = screen.getByRole('alert')
    expect(alert).toBeInTheDocument()
    expect(alert).toHaveTextContent(/broker adapter configuration/i)
  })

  it('shows "No closed trades yet" when the list is empty', () => {
    withData([])
    render(<ExitTypeCard />)
    expect(screen.getByText(/no closed trades yet/i)).toBeInTheDocument()
  })

  it('shows loading skeleton while data is loading', () => {
    mockUseExitTypes.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useExitTypes>)
    render(<ExitTypeCard />)
    expect(screen.getByRole('status', { name: /loading exit type data/i })).toBeInTheDocument()
  })

  it('shows error message on fetch failure', () => {
    mockUseExitTypes.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useExitTypes>)
    render(<ExitTypeCard />)
    expect(screen.getByText(/failed to load exit type data/i)).toBeInTheDocument()
  })
})
