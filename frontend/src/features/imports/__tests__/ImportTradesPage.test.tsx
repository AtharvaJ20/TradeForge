import { describe, it, expect } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AccountProvider } from '@/features/accounts/context/AccountContext'
import { ImportTradesPage } from '../ImportTradesPage'
import {
  IMPORT_SUCCESS_FIXTURE,
  IMPORT_PARTIAL_FIXTURE,
  IMPORT_HISTORY_FIXTURE,
  importPartialHandler,
  importFailedStatusHandler,
  importDuplicateHandler,
  importFileTooLargeHandler,
  importEmptyFileHandler,
  importUnrecognizedFormatHandler,
  importMissingProductTypeHandler,
  importHistoryEmptyHandler,
  importAccountInactiveHandler,
  accountsEmptyHandler,
  accountsNonZerodhaActiveHandler,
} from '@/__tests__/msw/handlers'
import { server } from '@/__tests__/msw/server'
import { http, HttpResponse } from 'msw'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BASE = 'http://localhost:8000'
const ZERODHA_ACCOUNT_ID = '00000000-0000-0000-0000-000000000001'
const NON_ZERODHA_ACCOUNT_ID = '00000000-0000-0000-0000-000000000003'

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/import']}>
      <AccountProvider>
        <Routes>
          <Route path="/import" element={<ImportTradesPage />} />
        </Routes>
      </AccountProvider>
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Helper: wait until account selector is populated and page is interactive
// ---------------------------------------------------------------------------

async function waitForPageReady() {
  await waitFor(() => {
    expect(screen.getByLabelText(/account/i)).toBeInTheDocument()
  })
}

// ---------------------------------------------------------------------------
// Helper: make a fake CSV File
// ---------------------------------------------------------------------------

function makeCsvFile(name = 'tradebook.csv', size?: number): File {
  const content = 'symbol,qty\nRELIANCE,10\n'
  const file = new File([content], name, { type: 'text/csv' })
  if (size !== undefined) {
    Object.defineProperty(file, 'size', { value: size, configurable: true })
  }
  return file
}

// ---------------------------------------------------------------------------
// Helper: select Zerodha account + attach a CSV file
// ---------------------------------------------------------------------------

async function selectAccountAndFile(
  user: ReturnType<typeof userEvent.setup>,
  accountId = ZERODHA_ACCOUNT_ID,
  file = makeCsvFile(),
) {
  await user.selectOptions(screen.getByLabelText(/account/i), accountId)
  const input = screen.getByLabelText(/broker csv file/i) as HTMLInputElement
  await user.upload(input, file)
}

// ===========================================================================
// Tests
// ===========================================================================

describe('F-17-01: Page renders upload form with account selector and file input', () => {
  it('shows account selector, file input, and Import button', async () => {
    renderPage()
    await waitForPageReady()

    expect(screen.getByLabelText(/account/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/broker csv file/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^import$/i })).toBeInTheDocument()
  })
})

describe('F-17-02: Non-Zerodha active account → guard note and disabled button', () => {
  it('shows Zerodha-only note and Import button is disabled', async () => {
    server.use(accountsNonZerodhaActiveHandler)
    renderPage()
    await waitForPageReady()

    await userEvent.setup().selectOptions(
      screen.getByLabelText(/account/i),
      NON_ZERODHA_ACCOUNT_ID,
    )

    expect(
      screen.getByRole('note', { hidden: false }) ??
        screen.getByText(/zerodha accounts only/i),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^import$/i })).toBeDisabled()
  })
})

describe('F-17-03: No file selected → Import button disabled', () => {
  it('Import button is disabled when no file is chosen', async () => {
    renderPage()
    await waitForPageReady()

    await userEvent.setup().selectOptions(screen.getByLabelText(/account/i), ZERODHA_ACCOUNT_ID)

    expect(screen.getByRole('button', { name: /^import$/i })).toBeDisabled()
  })

  it('Import button is disabled when no account is selected (even with a file chosen)', async () => {
    // Return an empty accounts list so selectedAccount is null and the auto-select
    // useEffect never fires — accountId stays '' throughout the test.
    server.use(accountsEmptyHandler)
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    // Upload a CSV file so that account absence is the only disabling factor
    await user.upload(screen.getByLabelText(/broker csv file/i) as HTMLInputElement, makeCsvFile())

    expect(screen.getByRole('button', { name: /^import$/i })).toBeDisabled()
  })
})

describe('F-17-04: Non-CSV file → file error shown', () => {
  it('shows file error for non-CSV file', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await user.selectOptions(screen.getByLabelText(/account/i), ZERODHA_ACCOUNT_ID)
    const input = screen.getByLabelText(/broker csv file/i) as HTMLInputElement
    const txtFile = new File(['data'], 'report.txt', { type: 'text/plain' })
    // Use fireEvent.change to bypass userEvent's accept-attribute filtering
    fireEvent.change(input, { target: { files: [txtFile] } })

    expect(await screen.findByText(/please select a csv file/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^import$/i })).toBeDisabled()
  })
})

describe('F-17-05: Zerodha account + CSV file → Import button enabled', () => {
  it('Import button becomes enabled', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)

    expect(screen.getByRole('button', { name: /^import$/i })).toBeEnabled()
  })
})

describe('F-17-06: COMPLETE import → success banner', () => {
  it('shows fills ingested count in success banner', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    // Wait for the status banner to appear, then verify count is within it
    await waitFor(() => {
      expect(screen.getByRole('status')).toBeInTheDocument()
    })
    const banner = screen.getByRole('status')
    expect(
      within(banner).getByText(new RegExp(`${IMPORT_SUCCESS_FIXTURE.fills_ingested}`, 'i')),
    ).toBeInTheDocument()
  })
})

describe('F-17-07: PARTIAL import → warning banner', () => {
  it('shows fills ingested and row errors in warning banner', async () => {
    server.use(importPartialHandler)
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    // Wait for status banner then scope queries within it
    await waitFor(() => {
      expect(screen.getByRole('status')).toBeInTheDocument()
    })
    const banner = screen.getByRole('status')
    expect(
      within(banner).getByText(new RegExp(`${IMPORT_PARTIAL_FIXTURE.fills_ingested}`, 'i')),
    ).toBeInTheDocument()
    expect(
      within(banner).getByText(new RegExp(`${IMPORT_PARTIAL_FIXTURE.row_errors}`, 'i')),
    ).toBeInTheDocument()
  })
})

describe('F-17-08: FAILED import → error alert', () => {
  it('shows import failed message', async () => {
    server.use(importFailedStatusHandler)
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
    expect(screen.getByText(/import failed/i)).toBeInTheDocument()
  })
})

describe('F-17-09: DUPLICATE_IMPORT error → specific message', () => {
  it('shows already imported message', async () => {
    server.use(importDuplicateHandler)
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(screen.getByText(/already been imported/i)).toBeInTheDocument()
    })
  })
})

describe('F-17-10: FILE_TOO_LARGE error → specific message', () => {
  it('shows file too large message', async () => {
    server.use(importFileTooLargeHandler)
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(screen.getByText(/file is too large/i)).toBeInTheDocument()
    })
  })
})

describe('F-17-10b: ACCOUNT_INACTIVE error → inline inactive message', () => {
  it('shows account inactive message', async () => {
    server.use(importAccountInactiveHandler)
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(screen.getByText(/this account is inactive/i)).toBeInTheDocument()
    })
  })
})

describe('F-17-11: In-flight submit → button shows Importing…', () => {
  it('button text changes to Importing… while request is pending', async () => {
    let resolveRequest!: (value: Response) => void
    const pendingRequest = new Promise<Response>((res) => {
      resolveRequest = res
    })
    server.use(
      http.post(`${BASE}/v1/accounts/:accountId/import`, () => pendingRequest),
    )

    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    // Don't await the click — the request hangs
    void user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /importing…/i })).toBeDisabled()
    })

    // Release the pending request so MSW doesn't leak
    resolveRequest(HttpResponse.json(IMPORT_SUCCESS_FIXTURE, { status: 201 }) as unknown as Response)
  })
})

describe('F-17-12: After success → Import another file button appears', () => {
  it('shows Import another file button after successful import', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /import another file/i })).toBeInTheDocument()
    })
  })
})

describe('F-17-13: Import another file → resets form', () => {
  it('clears file and result after clicking Import another file', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /import another file/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /import another file/i }))

    // Success banner gone, Import button back
    await waitFor(() => {
      expect(screen.queryByRole('status')).toBeNull()
      expect(screen.getByRole('button', { name: /^import$/i })).toBeInTheDocument()
    })
  })
})

describe('F-17-14: After successful import → history list refreshes', () => {
  it('fetches history again after import (historyTick increments)', async () => {
    let callCount = 0
    server.use(
      http.get(`${BASE}/v1/imports`, () => {
        callCount += 1
        return HttpResponse.json(IMPORT_HISTORY_FIXTURE)
      }),
    )

    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await waitFor(() => expect(callCount).toBe(1))

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(callCount).toBeGreaterThanOrEqual(2)
    })
  })
})

describe('F-17-15: History loads on mount and shows records', () => {
  it('renders history table rows from the fixture', async () => {
    renderPage()
    await waitForPageReady()

    await waitFor(() => {
      expect(screen.getByText(IMPORT_HISTORY_FIXTURE[0].file_name!)).toBeInTheDocument()
    })
    expect(screen.getByText(IMPORT_HISTORY_FIXTURE[1].file_name!)).toBeInTheDocument()
  })
})

describe('F-17-16: Empty history → no-imports message', () => {
  it('shows no imports message when history is empty', async () => {
    server.use(importHistoryEmptyHandler)
    renderPage()
    await waitForPageReady()

    await waitFor(() => {
      expect(screen.getByText(/no imports yet/i)).toBeInTheDocument()
    })
  })
})

describe('F-17-17: EMPTY_FILE error → specific message', () => {
  it('shows empty file message', async () => {
    server.use(importEmptyFileHandler)
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(screen.getByText(/no data rows/i)).toBeInTheDocument()
    })
  })
})

describe('F-17-18: UNRECOGNIZED_FILE_FORMAT error → specific message', () => {
  it('shows unrecognized format message', async () => {
    server.use(importUnrecognizedFormatHandler)
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(screen.getByText(/file format not recognised/i)).toBeInTheDocument()
    })
  })
})

describe('F-17-19: MISSING_PRODUCT_TYPE → product type hint selector shown', () => {
  it('reveals F&O product type selector after MISSING_PRODUCT_TYPE error', async () => {
    server.use(importMissingProductTypeHandler)
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    await selectAccountAndFile(user)
    await user.click(screen.getByRole('button', { name: /^import$/i }))

    await waitFor(() => {
      expect(screen.getByLabelText(/f.o product type/i)).toBeInTheDocument()
    })
  })
})

describe('F-17-20: File > 5 MB → client-side size warning', () => {
  it('shows size warning for large file without blocking submission', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitForPageReady()

    const largeFile = makeCsvFile('big.csv', 6 * 1024 * 1024)
    await selectAccountAndFile(user, ZERODHA_ACCOUNT_ID, largeFile)

    await waitFor(() => {
      expect(screen.getByText(/unusually large/i)).toBeInTheDocument()
    })
    // Import button should still be enabled (warning, not error)
    expect(screen.getByRole('button', { name: /^import$/i })).toBeEnabled()
  })
})
