import { useEffect, useRef } from 'react'
import { formatIst } from '@/lib/utils'
import { useAuditHistory } from '../hooks/useAuditHistory'
import type { AuditEntry, AuditGroup } from '../types'

interface AuditHistoryDrawerProps {
  tradeId: string
  isOpen: boolean
  onClose: () => void
}

const GROUP_WINDOW_MS = 5 * 60 * 1000 // 5 minutes

function groupEntries(entries: AuditEntry[]): AuditGroup[] {
  const groups: AuditGroup[] = []
  for (const entry of entries) {
    const last = groups[groups.length - 1]
    const entryTime = new Date(entry.changed_at).getTime()
    const groupTime = last ? new Date(last.groupedAt).getTime() : 0
    if (last && entryTime - groupTime <= GROUP_WINDOW_MS) {
      last.entries.push(entry)
    } else {
      groups.push({ groupedAt: entry.changed_at, entries: [entry] })
    }
  }
  return groups
}

/** C-08 AuditHistoryDrawer — slide-in drawer showing grouped version history. */
export function AuditHistoryDrawer({ tradeId, isOpen, onClose }: AuditHistoryDrawerProps) {
  const { data, isLoading } = useAuditHistory(tradeId, isOpen)
  const closeBtnRef = useRef<HTMLButtonElement>(null)
  const backdropRef = useRef<HTMLDivElement>(null)

  // Trap focus and move it to close button when drawer opens
  useEffect(() => {
    if (isOpen) {
      closeBtnRef.current?.focus()
    }
  }, [isOpen])

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const groups = data ? groupEntries(data) : []

  return (
    <>
      {/* Backdrop */}
      <div
        ref={backdropRef}
        className="fixed inset-0 z-40 bg-black/30"
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Drawer panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Version history"
        className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col bg-surface-base shadow-xl"
      >
        <header className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="font-semibold text-text-primary">Version History</h2>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            aria-label="Close version history"
            className="rounded-md p-1 text-text-secondary transition-colors hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {isLoading && (
            <p className="text-sm text-text-secondary" role="status">
              Loading history…
            </p>
          )}

          {!isLoading && groups.length === 0 && (
            <p className="text-sm text-text-secondary">No changes recorded yet.</p>
          )}

          {groups.map((group, gi) => (
            <div key={gi} className="mb-6">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                {formatIst(group.groupedAt)}
              </p>
              <ul className="space-y-3">
                {group.entries.map((entry, ei) => (
                  <li key={ei} className="rounded-md border border-border bg-surface-subtle p-3 text-sm">
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-medium text-text-primary">{entry.field_name}</span>
                      {entry.change_reason && (
                        <span className="shrink-0 text-xs text-text-tertiary italic">
                          "{entry.change_reason}"
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex gap-3 text-xs text-text-secondary">
                      <span className="line-through">{entry.previous_value ?? '—'}</span>
                      <span>→</span>
                      <span className="text-text-primary">{entry.new_value ?? '—'}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
