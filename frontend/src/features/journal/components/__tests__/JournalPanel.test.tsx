import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { JournalPanel } from '../JournalPanel'
import type { JournalEntry } from '../../types'

// Mock all hooks so the component test doesn't need a QueryClient or MSW
vi.mock('../../hooks/useJournalEntry', () => ({
  useJournalEntry: vi.fn(),
  journalKeys: {
    entry: (id: string) => ['journal', 'entry', id] as const,
    audit: (id: string) => ['journal', 'audit', id] as const,
  },
}))
vi.mock('../../hooks/useUpsertJournalEntry', () => ({
  useUpsertJournalEntry: vi.fn(),
}))
vi.mock('../../hooks/useAuditHistory', () => ({
  useAuditHistory: vi.fn(() => ({ data: [], isLoading: false })),
}))
vi.mock('../../hooks/useDeleteAttachment', () => ({
  useDeleteAttachment: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

import { useJournalEntry } from '../../hooks/useJournalEntry'
import { useUpsertJournalEntry } from '../../hooks/useUpsertJournalEntry'

const TRADE = {
  id: 'trade-001',
  symbol: 'RELIANCE',
  exchange: 'NSE',
  tradeDate: '2026-08-23',
  firstFillAt: '2026-08-23T09:15:00Z',
  direction: 'LONG' as const,
  tradeType: 'MIS' as const,
  averageEntry: '500.00',
  totalEntryQuantity: '100',
}

const BASE_ENTRY: JournalEntry = {
  id: '00000000-0000-0000-0000-000000000001',
  trade_id: '00000000-0000-0000-0000-000000000002',
  planned_entry: '500.00',
  planned_stop: '490.00',
  planned_target: '520.00',
  planned_risk_amount: '1000.00',
  setup_name: 'Bull flag',
  notes: 'Good execution',
  discipline_score: 8,
  mistakes: [],
  emotion_before: 'CALM',
  emotion_during: 'CONFIDENT',
  emotion_after: 'CALM',
  pnl: {
    status: 'PENDING_CALCULATION',
    net_pnl: null,
    gross_pnl: null,
    total_charges: null,
    r_multiple: null,
  },
  attachments: [],
  created_at: '2026-08-23T09:00:00Z',
  updated_at: '2026-08-23T09:00:00Z',
}

const mockUpsert = vi.fn()

beforeEach(() => {
  vi.mocked(useUpsertJournalEntry).mockReturnValue({
    mutateAsync: mockUpsert,
    isPending: false,
  } as ReturnType<typeof useUpsertJournalEntry>)
})

describe('JournalPanel — loading state', () => {
  it('shows skeleton while loading', () => {
    vi.mocked(useJournalEntry).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    } as ReturnType<typeof useJournalEntry>)
    render(<JournalPanel trade={TRADE} />)
    expect(document.querySelector('[role="presentation"]')).not.toBeNull()
  })
})

describe('JournalPanel — empty state', () => {
  beforeEach(() => {
    vi.mocked(useJournalEntry).mockReturnValue({
      data: null,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as ReturnType<typeof useJournalEntry>)
  })

  it('shows empty state CTAs when no entry exists', () => {
    render(<JournalPanel trade={TRADE} />)
    expect(screen.getByText(/no journal entry yet/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /quick capture/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /full notes/i })).toBeInTheDocument()
  })

  it('opens quick capture form on CTA click', async () => {
    render(<JournalPanel trade={TRADE} />)
    await userEvent.click(screen.getByRole('button', { name: /quick capture/i }))
    expect(screen.getByRole('radiogroup', { name: /discipline score/i })).toBeInTheDocument()
  })

  it('opens full form on Full Notes CTA click', async () => {
    render(<JournalPanel trade={TRADE} />)
    await userEvent.click(screen.getByRole('button', { name: /full notes/i }))
    expect(screen.getByLabelText(/planned stop/i)).toBeInTheDocument()
  })
})

describe('JournalPanel — entry exists', () => {
  beforeEach(() => {
    vi.mocked(useJournalEntry).mockReturnValue({
      data: BASE_ENTRY,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as ReturnType<typeof useJournalEntry>)
  })

  it('shows setup name and notes in read mode', () => {
    render(<JournalPanel trade={TRADE} />)
    expect(screen.getByText('Bull flag')).toBeInTheDocument()
    expect(screen.getByText('Good execution')).toBeInTheDocument()
  })

  it('shows PENDING_CALCULATION P&L block', () => {
    render(<JournalPanel trade={TRADE} />)
    expect(screen.getByText(/p&l calculating/i)).toBeInTheDocument()
  })

  it('shows Edit Journal and History buttons in footer', () => {
    render(<JournalPanel trade={TRADE} />)
    expect(screen.getByRole('button', { name: /edit journal/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /history/i })).toBeInTheDocument()
  })

  it('opens full form on Edit Journal click', async () => {
    render(<JournalPanel trade={TRADE} />)
    await userEvent.click(screen.getByRole('button', { name: /edit journal/i }))
    expect(screen.getByLabelText(/planned stop/i)).toBeInTheDocument()
  })

  it('shows PENDING_STOP P&L block with Add Stop CTA', () => {
    vi.mocked(useJournalEntry).mockReturnValue({
      data: {
        ...BASE_ENTRY,
        planned_stop: null,
        pnl: { status: 'PENDING_STOP', net_pnl: null, gross_pnl: null, total_charges: null, r_multiple: null },
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as ReturnType<typeof useJournalEntry>)
    render(<JournalPanel trade={TRADE} />)
    expect(screen.getByText(/set a stop to unlock r-multiple/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add stop/i })).toBeInTheDocument()
  })

  it('opens full form when Add Stop CTA is clicked', async () => {
    vi.mocked(useJournalEntry).mockReturnValue({
      data: {
        ...BASE_ENTRY,
        planned_stop: null,
        pnl: { status: 'PENDING_STOP', net_pnl: null, gross_pnl: null, total_charges: null, r_multiple: null },
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as ReturnType<typeof useJournalEntry>)
    render(<JournalPanel trade={TRADE} />)
    await userEvent.click(screen.getByRole('button', { name: /add stop/i }))
    await waitFor(() => {
      expect(screen.getByLabelText(/planned stop/i)).toBeInTheDocument()
    })
  })
})

describe('JournalPanel — error state', () => {
  it('shows error state with retry button', () => {
    vi.mocked(useJournalEntry).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch: vi.fn(),
    } as ReturnType<typeof useJournalEntry>)
    render(<JournalPanel trade={TRADE} />)
    expect(screen.getByText(/couldn't load journal entry/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})
