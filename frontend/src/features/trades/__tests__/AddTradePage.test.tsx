import { describe, it, expect } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { AccountProvider } from '@/features/accounts/context/AccountContext'
import { AddTradePage } from '../AddTradePage'
import {
  ACCOUNTS_LIST_FIXTURE,
  TRADE_OPEN_FIXTURE,
  createTradeInstrumentNotFoundHandler,
} from '@/__tests__/msw/handlers'
import { server } from '@/__tests__/msw/server'

// ---------------------------------------------------------------------------
// /trades stub: reads success message from navigation state so F-16-12 can
// verify the toast after navigation.
// ---------------------------------------------------------------------------

function TradesRoute() {
  const location = useLocation()
  const state = location.state as { successMessage?: string } | null
  return (
    <div>
      {state?.successMessage && (
        <div role="status">{state.successMessage}</div>
      )}
      Trades list page
    </div>
  )
}

// ---------------------------------------------------------------------------
// Render helper: wraps AddTradePage with AccountProvider and MemoryRouter.
// Includes /trades route so navigation after success can be verified.
// ---------------------------------------------------------------------------

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/trades/new']}>
      <AccountProvider>
        <Routes>
          <Route path="/trades/new" element={<AddTradePage />} />
          <Route path="/trades" element={<TradesRoute />} />
        </Routes>
      </AccountProvider>
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Helper: waits for the page to be ready (account selector loaded)
// ---------------------------------------------------------------------------

async function waitForPageReady() {
  await waitFor(() => {
    expect(screen.getByLabelText(/account/i)).toBeInTheDocument()
  })
}

// ---------------------------------------------------------------------------
// Helper: fills the instrument section with valid EQ values
// ---------------------------------------------------------------------------

async function fillInstrumentSection(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByLabelText(/account/i), ACCOUNTS_LIST_FIXTURE[0].id)
  await user.type(screen.getByLabelText(/symbol/i), 'RELIANCE')
  await user.selectOptions(screen.getByLabelText(/exchange segment/i), 'NSE_EQ')
  await user.selectOptions(screen.getByLabelText(/instrument type/i), 'EQ')
  await user.selectOptions(screen.getByLabelText(/product type/i), 'MIS')
}

// ---------------------------------------------------------------------------
// Helper: fills the first fill row with valid values
// ---------------------------------------------------------------------------

async function fillFirstRow(user: ReturnType<typeof userEvent.setup>) {
  const rows = screen.getAllByTestId('fill-row')
  await user.selectOptions(within(rows[0]).getByLabelText(/side/i), 'BUY')
  await user.clear(within(rows[0]).getByLabelText(/quantity/i))
  await user.type(within(rows[0]).getByLabelText(/quantity/i), '10')
  await user.clear(within(rows[0]).getByLabelText(/price/i))
  await user.type(within(rows[0]).getByLabelText(/price/i), '500')
  fireEvent.change(within(rows[0]).getByLabelText(/date/i), {
    target: { value: '2026-09-06' },
  })
  fireEvent.change(within(rows[0]).getByLabelText(/time/i), {
    target: { value: '10:15' },
  })
}

// ---------------------------------------------------------------------------
// F-16-01: account selector populated from AccountContext
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-01: account selector populated from AccountContext', () => {
  it('renders account options from AccountContext, active accounts visible', async () => {
    renderPage()
    await waitForPageReady()

    const accountSelect = screen.getByLabelText(/account/i)
    const options = Array.from(accountSelect.querySelectorAll('option'))
    const optionValues = options.map((o) => o.value)

    // Active account appears
    expect(optionValues).toContain(ACCOUNTS_LIST_FIXTURE[0].id)
    // Inactive account does NOT appear (active-only filter)
    expect(optionValues).not.toContain(ACCOUNTS_LIST_FIXTURE[1].id)
  })
})

// ---------------------------------------------------------------------------
// F-16-02: expiry date hidden for EQ, shown for FUT
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-02: expiry date visibility', () => {
  it('hides expiry date for EQ and shows it for FUT', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    // EQ: expiry date not present
    await user.selectOptions(screen.getByLabelText(/instrument type/i), 'EQ')
    expect(screen.queryByLabelText(/expiry date/i)).not.toBeInTheDocument()

    // FUT: expiry date shown
    await user.selectOptions(screen.getByLabelText(/instrument type/i), 'FUT')
    expect(screen.getByLabelText(/expiry date/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-16-03: strike price hidden for EQ, shown for CE
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-03: strike price visibility', () => {
  it('hides strike price for EQ and shows it for CE', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    // EQ: strike price not present
    await user.selectOptions(screen.getByLabelText(/instrument type/i), 'EQ')
    expect(screen.queryByLabelText(/strike price/i)).not.toBeInTheDocument()

    // CE: strike price shown
    await user.selectOptions(screen.getByLabelText(/instrument type/i), 'CE')
    expect(screen.getByLabelText(/strike price/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-16-04: "Add fill" button appends a second fill row
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-04: Add fill appends second fill row', () => {
  it('appends a second fill row when "Add fill" is clicked', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    expect(screen.getAllByTestId('fill-row')).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: /add fill/i }))

    expect(screen.getAllByTestId('fill-row')).toHaveLength(2)
  })
})

// ---------------------------------------------------------------------------
// F-16-05: valid submit calls POST /v1/trades with correct body
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-05: valid submit posts correct body', () => {
  it('calls POST /v1/trades with correct account_id, instrument, product_type, fills', async () => {
    let capturedBody: unknown = null
    server.use(
      http.post('http://localhost:8000/v1/trades', async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json(TRADE_OPEN_FIXTURE, { status: 201 })
      }),
    )

    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await fillInstrumentSection(user)
    await fillFirstRow(user)

    await user.click(screen.getByRole('button', { name: /add trade/i }))

    await waitFor(() => {
      expect(capturedBody).not.toBeNull()
    })

    const body = capturedBody as Record<string, unknown>
    expect(body.account_id).toBe(ACCOUNTS_LIST_FIXTURE[0].id)
    expect(body.instrument).toMatchObject({
      symbol: 'RELIANCE',
      exchange_segment: 'NSE_EQ',
      instrument_type: 'EQ',
    })
    expect(body.product_type).toBe('MIS')
    const fills = body.fills as Array<Record<string, unknown>>
    expect(fills).toHaveLength(1)
    expect(fills[0].side).toBe('BUY')
    expect(fills[0].quantity).toBe('10')
    expect(fills[0].price).toBe('500')
    expect(fills[0].fill_timestamp).toMatch(/^2026-09-06T10:15:00\+05:30$/)
  })
})

// ---------------------------------------------------------------------------
// F-16-06: symbol forced to uppercase
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-06: symbol forced to uppercase', () => {
  it('converts typed symbol to uppercase', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    const symbolInput = screen.getByLabelText(/symbol/i)
    await user.type(symbolInput, 'reliance')

    expect(symbolInput).toHaveValue('RELIANCE')
  })
})

// ---------------------------------------------------------------------------
// F-16-07: missing symbol shows validation error, no API call
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-07: missing symbol shows validation error', () => {
  it('shows symbol required error and does not call API when symbol is blank', async () => {
    let apiCalled = false
    server.use(
      http.post('http://localhost:8000/v1/trades', () => {
        apiCalled = true
        return HttpResponse.json(TRADE_OPEN_FIXTURE, { status: 201 })
      }),
    )

    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    // Fill everything except symbol
    await user.selectOptions(screen.getByLabelText(/account/i), ACCOUNTS_LIST_FIXTURE[0].id)
    await user.selectOptions(screen.getByLabelText(/exchange segment/i), 'NSE_EQ')
    await user.selectOptions(screen.getByLabelText(/instrument type/i), 'EQ')
    await user.selectOptions(screen.getByLabelText(/product type/i), 'MIS')
    await fillFirstRow(user)

    await user.click(screen.getByRole('button', { name: /add trade/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/symbol is required/i)
    })
    expect(apiCalled).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// F-16-08: fills out of chronological order shows inline error
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-08: chronological order violation shows inline error', () => {
  it('shows chronological error on second fill row when timestamps are out of order', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await fillInstrumentSection(user)

    // Fill row 1: 10:15
    await fillFirstRow(user)

    // Add second fill row
    await user.click(screen.getByRole('button', { name: /add fill/i }))

    const rows = screen.getAllByTestId('fill-row')
    await user.selectOptions(within(rows[1]).getByLabelText(/side/i), 'SELL')
    await user.clear(within(rows[1]).getByLabelText(/quantity/i))
    await user.type(within(rows[1]).getByLabelText(/quantity/i), '10')
    await user.clear(within(rows[1]).getByLabelText(/price/i))
    await user.type(within(rows[1]).getByLabelText(/price/i), '510')
    // Use an earlier timestamp for the second fill
    fireEvent.change(within(rows[1]).getByLabelText(/date/i), {
      target: { value: '2026-09-06' },
    })
    fireEvent.change(within(rows[1]).getByLabelText(/time/i), {
      target: { value: '09:30' },
    })

    await user.click(screen.getByRole('button', { name: /add trade/i }))

    await waitFor(() => {
      expect(screen.getAllByRole('alert').some((el) => /chronological|order/i.test(el.textContent ?? ''))).toBe(true)
    })
  })
})

// ---------------------------------------------------------------------------
// F-16-09: quantity ≤ 0 shows validation error
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-09: quantity ≤ 0 shows validation error', () => {
  it('shows quantity validation error when quantity is 0', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await fillInstrumentSection(user)

    const rows = screen.getAllByTestId('fill-row')
    await user.selectOptions(within(rows[0]).getByLabelText(/side/i), 'BUY')

    // Set quantity to 0
    const quantityInput = within(rows[0]).getByLabelText(/quantity/i)
    await user.clear(quantityInput)
    await user.type(quantityInput, '0')

    await user.clear(within(rows[0]).getByLabelText(/price/i))
    await user.type(within(rows[0]).getByLabelText(/price/i), '500')
    fireEvent.change(within(rows[0]).getByLabelText(/date/i), {
      target: { value: '2026-09-06' },
    })
    fireEvent.change(within(rows[0]).getByLabelText(/time/i), {
      target: { value: '10:15' },
    })

    await user.click(screen.getByRole('button', { name: /add trade/i }))

    await waitFor(() => {
      expect(
        screen.getAllByRole('alert').some((el) => /quantity/i.test(el.textContent ?? '')),
      ).toBe(true)
    })
  })
})

// ---------------------------------------------------------------------------
// F-16-10: submit button disabled while in-flight
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-10: submit button disabled while request is in flight', () => {
  it('disables the submit button while the request is pending', async () => {
    let resolveRequest!: () => void
    server.use(
      http.post('http://localhost:8000/v1/trades', async () => {
        await new Promise<void>((resolve) => {
          resolveRequest = resolve
        })
        return HttpResponse.json(TRADE_OPEN_FIXTURE, { status: 201 })
      }),
    )

    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await fillInstrumentSection(user)
    await fillFirstRow(user)

    await user.click(screen.getByRole('button', { name: /add trade/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add trade|submitting/i })).toBeDisabled()
    })

    // Resolve to clean up
    resolveRequest()
  })
})

// ---------------------------------------------------------------------------
// F-16-11: INSTRUMENT_NOT_FOUND shows inline error (not toast)
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-11: INSTRUMENT_NOT_FOUND shows inline error', () => {
  it('shows inline error message when API returns INSTRUMENT_NOT_FOUND', async () => {
    server.use(createTradeInstrumentNotFoundHandler)

    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await fillInstrumentSection(user)
    await fillFirstRow(user)

    await user.click(screen.getByRole('button', { name: /add trade/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/instrument_not_found/i)
    })
  })
})

// ---------------------------------------------------------------------------
// F-16-12: on success, shows success toast
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-12: on success, shows success toast', () => {
  it('shows "Trade added successfully." toast after successful submission', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await fillInstrumentSection(user)
    await fillFirstRow(user)

    await user.click(screen.getByRole('button', { name: /add trade/i }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('Trade added successfully.')
    })
  })
})

// ---------------------------------------------------------------------------
// F-16-13: FUT → CNC option disabled; EQ → NRML option disabled (D1)
// ---------------------------------------------------------------------------

describe('AddTradePage — F-16-13: D1 product type option disabling', () => {
  it('disables CNC when instrument type is FUT, disables NRML when instrument type is EQ', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    const productTypeSelect = screen.getByLabelText(/product type/i)

    // FUT: CNC should be disabled
    await user.selectOptions(screen.getByLabelText(/instrument type/i), 'FUT')
    const cncOptionFut = Array.from(productTypeSelect.querySelectorAll('option')).find(
      (o) => o.value === 'CNC',
    )
    expect(cncOptionFut).toBeDefined()
    expect(cncOptionFut).toBeDisabled()

    // EQ: NRML should be disabled
    await user.selectOptions(screen.getByLabelText(/instrument type/i), 'EQ')
    const nrmlOptionEq = Array.from(productTypeSelect.querySelectorAll('option')).find(
      (o) => o.value === 'NRML',
    )
    expect(nrmlOptionEq).toBeDefined()
    expect(nrmlOptionEq).toBeDisabled()
  })
})
