import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuditPromptInline } from '../AuditPromptInline'

/** Effectively infinite — prevents auto-dismiss racing with non-timer tests. */
const NO_AUTODISMISS = 999_999

// ---------------------------------------------------------------------------
// Idle state
// ---------------------------------------------------------------------------

describe('AuditPromptInline — idle state', () => {
  it('renders input, Add button, and Dismiss button', () => {
    render(<AuditPromptInline onSubmit={vi.fn()} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />)
    expect(screen.getByRole('textbox', { name: /reason for change/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^add$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument()
  })

  it('shows the prompt copy', () => {
    render(<AuditPromptInline onSubmit={vi.fn()} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />)
    expect(screen.getByText(/entry saved/i)).toBeInTheDocument()
    expect(screen.getByText(/why did you change it/i)).toBeInTheDocument()
  })

  it('Add button is disabled when input is empty', () => {
    render(<AuditPromptInline onSubmit={vi.fn()} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />)
    expect(screen.getByRole('button', { name: /^add$/i })).toBeDisabled()
  })

  it('Add button is disabled when input is only whitespace', async () => {
    const user = userEvent.setup()
    render(<AuditPromptInline onSubmit={vi.fn()} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />)
    await user.type(screen.getByRole('textbox'), '   ')
    expect(screen.getByRole('button', { name: /^add$/i })).toBeDisabled()
  })

  it('Add button enables when input has non-whitespace text', async () => {
    const user = userEvent.setup()
    render(<AuditPromptInline onSubmit={vi.fn()} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />)
    await user.type(screen.getByRole('textbox'), 'Corrected stop')
    expect(screen.getByRole('button', { name: /^add$/i })).not.toBeDisabled()
  })
})

// ---------------------------------------------------------------------------
// Dismiss button
// ---------------------------------------------------------------------------

describe('AuditPromptInline — Dismiss', () => {
  it('calls onDismiss and removes the banner', async () => {
    const user = userEvent.setup()
    const onDismiss = vi.fn()
    render(<AuditPromptInline onSubmit={vi.fn()} onDismiss={onDismiss} autoDismissMs={NO_AUTODISMISS} />)
    await user.click(screen.getByRole('button', { name: /dismiss/i }))
    expect(onDismiss).toHaveBeenCalledOnce()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Add (submit) behaviour  — all use real timers and NO_AUTODISMISS
// ---------------------------------------------------------------------------

describe('AuditPromptInline — Add', () => {
  it('calls onSubmit with the trimmed reason', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<AuditPromptInline onSubmit={onSubmit} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />)
    await user.type(screen.getByRole('textbox'), '  Corrected the stop  ')
    await user.click(screen.getByRole('button', { name: /^add$/i }))
    expect(onSubmit).toHaveBeenCalledWith('Corrected the stop')
  })

  it('Enter key submits the reason', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<AuditPromptInline onSubmit={onSubmit} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />)
    await user.type(screen.getByRole('textbox'), 'via enter{Enter}')
    expect(onSubmit).toHaveBeenCalledWith('via enter')
  })

  it('shows "Reason added." after successful submit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<AuditPromptInline onSubmit={onSubmit} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />)
    await user.type(screen.getByRole('textbox'), 'my reason')
    await user.click(screen.getByRole('button', { name: /^add$/i }))
    await waitFor(() => expect(screen.getByText(/reason added/i)).toBeInTheDocument())
  })

  it('disables input and Dismiss button while submitting', async () => {
    let resolve!: () => void
    const onSubmit = vi.fn().mockReturnValue(new Promise<void>((r) => { resolve = r }))
    const user = userEvent.setup()
    render(<AuditPromptInline onSubmit={onSubmit} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />)
    await user.type(screen.getByRole('textbox'), 'reason')
    // Start the click but don't await — inspect the submitting state before resolution
    void user.click(screen.getByRole('button', { name: /^add$/i }))
    await waitFor(() => expect(screen.getByRole('textbox')).toBeDisabled())
    expect(screen.getByRole('button', { name: /dismiss/i })).toBeDisabled()
    resolve()
  })

  it('returns to idle on submit failure', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockRejectedValue(new Error('network'))
    render(<AuditPromptInline onSubmit={onSubmit} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />)
    await user.type(screen.getByRole('textbox'), 'reason')
    await user.click(screen.getByRole('button', { name: /^add$/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /^add$/i })).toBeInTheDocument())
    expect(screen.getByRole('textbox')).not.toBeDisabled()
  })
})

// ---------------------------------------------------------------------------
// Auto-dismiss timer — all use fake timers (beforeEach / afterEach)
// fireEvent is used for synchronous DOM events inside fake-timer blocks
// (userEvent uses real setTimeout internally and stalls with frozen timers)
// ---------------------------------------------------------------------------

describe('AuditPromptInline — auto-dismiss', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('auto-dismisses after autoDismissMs', () => {
    const onDismiss = vi.fn()
    render(<AuditPromptInline onSubmit={vi.fn()} onDismiss={onDismiss} autoDismissMs={8000} />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
    act(() => { vi.advanceTimersByTime(8000) })
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(onDismiss).toHaveBeenCalledOnce()
  })

  it('does not auto-dismiss while input is focused', () => {
    const onDismiss = vi.fn()
    render(<AuditPromptInline onSubmit={vi.fn()} onDismiss={onDismiss} autoDismissMs={8000} />)
    // Use fireEvent (synchronous, no internal timer usage) to focus the input
    fireEvent.focus(screen.getByRole('textbox'))
    act(() => { vi.advanceTimersByTime(10_000) })
    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(onDismiss).not.toHaveBeenCalled()
  })

  it('unmounts 2 s after successful submit', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const { getByRole, queryByText } = render(
      <AuditPromptInline onSubmit={onSubmit} onDismiss={vi.fn()} autoDismissMs={NO_AUTODISMISS} />
    )
    fireEvent.change(getByRole('textbox'), { target: { value: 'reason' } })
    fireEvent.click(getByRole('button', { name: /^add$/i }))
    // Flush the async onSubmit resolution and React state updates (no timers needed)
    await act(async () => {})
    expect(screen.getByText(/reason added/i)).toBeInTheDocument()
    // Advance the 2 s unmount timer
    act(() => { vi.advanceTimersByTime(2000) })
    expect(queryByText(/reason added/i)).not.toBeInTheDocument()
  })
})
