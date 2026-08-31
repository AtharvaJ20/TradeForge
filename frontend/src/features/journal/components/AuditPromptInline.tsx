import { useEffect, useRef, useState } from 'react'

export interface AuditPromptInlineProps {
  /** Called with the trimmed reason string when the user clicks Add. */
  onSubmit: (reason: string) => Promise<void>
  /** Called when the banner dismisses without a reason (auto-dismiss or Dismiss button). */
  onDismiss: () => void
  /** Auto-dismiss delay in ms. Defaults to 8000. */
  autoDismissMs?: number
}

type Stage = 'idle' | 'submitting' | 'submitted'

const DEFAULT_MS = 8000

/** C-09 AuditPromptInline — G5 §4.3
 *
 *  Inline banner that appears after saving an edit to an existing entry.
 *  Lets the user optionally record a change reason, which is sent via a
 *  second PUT to the journal API so the audit log row carries the reason.
 *
 *  Timer behaviour:
 *  - Auto-dismisses after autoDismissMs if the user does not interact.
 *  - Paused while the text input has focus; resumes on blur.
 *  - Cleared permanently when the user submits or manually dismisses.
 */
export function AuditPromptInline({
  onSubmit,
  onDismiss,
  autoDismissMs = DEFAULT_MS,
}: AuditPromptInlineProps) {
  const [visible, setVisible] = useState(true)
  const [stage, setStage] = useState<Stage>('idle')
  const [reason, setReason] = useState('')
  const [isFocused, setIsFocused] = useState(false)

  // Mutable refs for timer bookkeeping — avoids stale closures in setTimeout
  const remainingRef = useRef(autoDismissMs)
  const startRef = useRef<number>(Date.now())
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Keep a stable ref to onDismiss so the timer callback is never stale
  const onDismissRef = useRef(onDismiss)
  useEffect(() => {
    onDismissRef.current = onDismiss
  })

  // Auto-dismiss timer — paused while input is focused or stage is not idle
  useEffect(() => {
    if (!visible || stage !== 'idle' || isFocused) {
      // Pause: record remaining duration and clear the running timer
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
        timerRef.current = null
        remainingRef.current = Math.max(0, remainingRef.current - (Date.now() - startRef.current))
      }
      return
    }

    // Resume: arm a timer for the remaining duration
    startRef.current = Date.now()
    timerRef.current = setTimeout(() => {
      setVisible(false)
      onDismissRef.current()
    }, remainingRef.current)

    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [visible, stage, isFocused])

  const handleDismiss = () => {
    if (timerRef.current !== null) clearTimeout(timerRef.current)
    setVisible(false)
    onDismiss()
  }

  const handleAdd = async () => {
    const trimmed = reason.trim()
    if (!trimmed) return
    if (timerRef.current !== null) clearTimeout(timerRef.current)
    setStage('submitting')
    try {
      await onSubmit(trimmed)
      setStage('submitted')
      setTimeout(() => setVisible(false), 2000)
    } catch {
      setStage('idle')
    }
  }

  if (!visible) return null

  if (stage === 'submitted') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex h-14 items-center rounded-md border border-success/30 bg-surface-success px-4 text-sm text-success-emphasis"
      >
        Reason added.
      </div>
    )
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex h-14 items-center gap-2 rounded-md border border-info/30 bg-surface-info px-3 text-sm"
    >
      <span className="shrink-0 text-info">
        Entry saved. Why did you change it?
      </span>
      <input
        type="text"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onKeyDown={(e) => { if (e.key === 'Enter') void handleAdd() }}
        placeholder="e.g. Corrected the stop level"
        disabled={stage === 'submitting'}
        aria-label="Reason for change (optional)"
        className="min-w-0 flex-1 rounded border border-border bg-surface px-2 py-1 text-sm text-text-primary placeholder:text-text-tertiary focus:outline focus:outline-2 focus:outline-border-focus disabled:opacity-50"
      />
      <button
        type="button"
        onClick={() => void handleAdd()}
        disabled={stage === 'submitting' || !reason.trim()}
        className="shrink-0 rounded-md bg-primary px-3 py-1 text-xs font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus disabled:opacity-40"
      >
        {stage === 'submitting' ? '…' : 'Add'}
      </button>
      <button
        type="button"
        onClick={handleDismiss}
        disabled={stage === 'submitting'}
        aria-label="Dismiss"
        className="shrink-0 text-text-secondary hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus disabled:opacity-50"
      >
        Dismiss
      </button>
    </div>
  )
}
