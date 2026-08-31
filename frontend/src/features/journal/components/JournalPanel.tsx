import { useState } from 'react'
import { formatDate, formatIst } from '@/lib/utils'
import { useJournalEntry } from '../hooks/useJournalEntry'
import { useUpsertJournalEntry } from '../hooks/useUpsertJournalEntry'
import type { TradeForJournal, JournalEntryWrite } from '../types'
import { SkeletonPnlBlock } from './SkeletonPnlBlock'
import { PnlStatusBlock } from './PnlStatusBlock'
import { TradeContextPanel } from './TradeContextPanel'
import { JournalQuickCapture } from './JournalQuickCapture'
import { JournalFullForm } from './JournalFullForm'
import { AuditPromptInline } from './AuditPromptInline'
import { AuditHistoryDrawer } from './AuditHistoryDrawer'
import { AttachmentGrid } from './AttachmentGrid'
import { AttachmentUploader } from './AttachmentUploader'

type FormMode = 'none' | 'quick' | 'full'

interface JournalPanelProps {
  trade: TradeForJournal
  onClose?: () => void
}

/** JournalPanel — composition root implementing the state matrix from UX spec §10. */
export function JournalPanel({ trade, onClose }: JournalPanelProps) {
  const [formMode, setFormMode] = useState<FormMode>('none')
  const [showAuditPrompt, setShowAuditPrompt] = useState(false)
  const [showAuditDrawer, setShowAuditDrawer] = useState(false)
  const [showUploader, setShowUploader] = useState(false)
  const [lastSavedData, setLastSavedData] = useState<JournalEntryWrite | null>(null)

  const { data: entry, isLoading, isError, refetch } = useJournalEntry(trade.id)
  const { mutateAsync: upsertEntry, isPending: isSaving } = useUpsertJournalEntry(trade.id)

  const entryExists = entry !== null && entry !== undefined
  const auditCount = 0 // optimistic count; will be accurate after audit fetch

  const handleSave = async (data: JournalEntryWrite, isEdit: boolean) => {
    await upsertEntry(data)
    setFormMode('none')
    if (isEdit) {
      setLastSavedData(data)
      setShowAuditPrompt(true)
    }
  }

  const handleSubmitReason = async (reason: string) => {
    if (!lastSavedData) return
    await upsertEntry({ ...lastSavedData, change_reason: reason })
    setShowAuditPrompt(false)
  }

  const handleDismissPrompt = () => {
    setShowAuditPrompt(false)
  }

  const handleAddStop = () => {
    setFormMode('full')
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col gap-4 p-4">
        <SkeletonPnlBlock />
        <div className="space-y-2">
          <div className="h-4 w-3/4 rounded bg-surface-subtle animate-shimmer [background-image:linear-gradient(90deg,var(--color-surface-subtle)_25%,var(--color-surface-neutral)_50%,var(--color-surface-subtle)_75%)] [background-size:200%_100%] motion-reduce:animate-none" />
          <div className="h-4 w-1/2 rounded bg-surface-subtle animate-shimmer [background-image:linear-gradient(90deg,var(--color-surface-subtle)_25%,var(--color-surface-neutral)_50%,var(--color-surface-subtle)_75%)] [background-size:200%_100%] motion-reduce:animate-none" />
        </div>
      </div>
    )
  }

  // Error state
  if (isError) {
    return (
      <div className="flex flex-col items-center gap-3 p-8 text-center">
        <p className="text-sm text-danger-emphasis">Couldn't load journal entry.</p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="text-sm text-primary underline-offset-2 hover:underline"
        >
          Try again
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Panel header */}
      <header className="flex h-12 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-semibold text-text-primary">{trade.symbol}</span>
          <span className="text-text-secondary">·</span>
          <span className="text-text-secondary">{formatDate(trade.tradeDate)}</span>
          <span className="text-text-secondary">·</span>
          <span
            className={
              trade.direction === 'LONG'
                ? 'text-success-emphasis font-medium'
                : 'text-danger-emphasis font-medium'
            }
          >
            {trade.direction === 'LONG' ? 'LONG ↑' : 'SHORT ↓'}
          </span>
          <span className="text-text-secondary">·</span>
          <span className="text-text-secondary">{trade.tradeType}</span>
        </div>
        <div className="flex items-center gap-2">
          {entryExists && (
            <button
              type="button"
              onClick={() => setFormMode('quick')}
              title="Quick capture"
              aria-label="Quick capture"
              className="rounded p-1 text-text-secondary hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus"
            >
              ⚡
            </button>
          )}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close journal panel"
              className="rounded p-1 text-text-secondary hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus"
            >
              ✕
            </button>
          )}
        </div>
      </header>

      {/* Body — scrollable */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* AuditPromptInline — appears after a save on existing entry */}
        {showAuditPrompt && (
          <AuditPromptInline
            onSubmit={handleSubmitReason}
            onDismiss={handleDismissPrompt}
          />
        )}

        {/* Trade context — always shown */}
        <TradeContextPanel
          trade={trade}
          plannedStop={entry?.planned_stop ?? null}
          plannedTarget={entry?.planned_target ?? null}
        />

        {/* State matrix §10 — form mode takes priority over entry-existence check */}
        {formMode === 'quick' ? (
          <section aria-label="Quick capture">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-text-primary">Quick Capture</h2>
              <button
                type="button"
                onClick={() => setFormMode('none')}
                aria-label="Close quick capture"
                className="text-text-secondary hover:text-text-primary"
              >
                ✕
              </button>
            </div>
            <JournalQuickCapture
              defaultValues={{
                discipline_score: entry?.discipline_score ?? undefined,
                emotion_after: entry?.emotion_after ?? undefined,
                mistakes: (entry?.mistakes ?? []) as string[],
              }}
              isSaving={isSaving}
              onSave={(data) => void handleSave(data, entryExists)}
              onExpandForm={() => setFormMode('full')}
            />
          </section>
        ) : formMode === 'full' ? (
          <section aria-label="Edit journal entry">
            <JournalFullForm
              entry={entry ?? null}
              trade={trade}
              isExisting={entryExists}
              isSaving={isSaving}
              onSave={(data) => void handleSave(data, entryExists)}
            />
            <button
              type="button"
              onClick={() => setFormMode('none')}
              className="mt-2 w-full rounded-md border border-border px-4 py-2 text-sm text-text-secondary hover:text-text-primary"
            >
              Cancel
            </button>
          </section>
        ) : !entryExists ? (
          /* Empty state — no entry and no form active */
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <span className="text-4xl" aria-hidden="true">📓</span>
            <div>
              <p className="font-semibold text-text-primary">No journal entry yet.</p>
              <p className="mt-1 text-sm text-text-secondary">
                Annotate this trade to track your planning and emotional state.
              </p>
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setFormMode('quick')}
                className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white"
              >
                Quick Capture
              </button>
              <button
                type="button"
                onClick={() => setFormMode('full')}
                className="rounded-md border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary"
              >
                Full Notes
              </button>
            </div>
          </div>
        ) : (
          /* Read mode — entry exists, formMode === 'none' */
          <>
            {/* P&L status */}
            <PnlStatusBlock
              status={entry.pnl.status}
              netPnl={entry.pnl.net_pnl}
              grossPnl={entry.pnl.gross_pnl}
              totalCharges={entry.pnl.total_charges}
              rMultiple={entry.pnl.r_multiple}
              onAddStop={entry.pnl.status === 'PENDING_STOP' ? handleAddStop : undefined}
            />

            {/* Read mode — annotation content */}
            <section aria-label="Journal entry" className="space-y-4">
              {entry.setup_name && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">Setup</p>
                  <p className="mt-1 text-sm text-text-primary">{entry.setup_name}</p>
                </div>
              )}
              {entry.notes && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">Notes</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-text-primary">{entry.notes}</p>
                </div>
              )}
              {entry.discipline_score !== null && entry.discipline_score !== undefined && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                    Discipline Score
                  </p>
                  <p className="mt-1 text-sm font-medium text-text-primary">
                    {entry.discipline_score} / 10
                  </p>
                </div>
              )}
              {entry.mistakes && entry.mistakes.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">Mistakes</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {entry.mistakes.map((m) => (
                      <span
                        key={m}
                        className="rounded-full border border-danger/30 bg-surface-danger px-2 py-0.5 text-xs text-danger-emphasis"
                      >
                        {m.replace(/_/g, ' ').toLowerCase()}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {(entry.emotion_before || entry.emotion_during || entry.emotion_after) && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">Emotions</p>
                  <dl className="mt-1 grid grid-cols-3 gap-2 text-sm">
                    {entry.emotion_before && (
                      <div>
                        <dt className="text-xs text-text-tertiary">Before</dt>
                        <dd className="text-text-primary">{entry.emotion_before}</dd>
                      </div>
                    )}
                    {entry.emotion_during && (
                      <div>
                        <dt className="text-xs text-text-tertiary">During</dt>
                        <dd className="text-text-primary">{entry.emotion_during}</dd>
                      </div>
                    )}
                    {entry.emotion_after && (
                      <div>
                        <dt className="text-xs text-text-tertiary">After</dt>
                        <dd className="text-text-primary">{entry.emotion_after}</dd>
                      </div>
                    )}
                  </dl>
                </div>
              )}
            </section>

            {/* Attachments */}
            {entry.attachments && entry.attachments.length > 0 && (
              <section aria-label="Attachments" className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">Attachments</p>
                <AttachmentGrid tradeId={trade.id} attachments={entry.attachments} />
              </section>
            )}

            {/* Add attachment trigger */}
            {!showUploader && (
              <button
                type="button"
                onClick={() => setShowUploader(true)}
                className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus"
              >
                <span className="text-lg" aria-hidden="true">+</span>
                Add attachment
              </button>
            )}
            {showUploader && (
              <AttachmentUploader
                tradeId={trade.id}
                onSuccess={() => setShowUploader(false)}
              />
            )}
          </>
        )}
      </div>

      {/* Footer — only when entry exists and form is closed */}
      {entryExists && formMode === 'none' && (
        <footer className="flex h-14 items-center justify-between border-t border-border px-4">
          <button
            type="button"
            onClick={() => setFormMode('full')}
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-text-primary hover:bg-surface-subtle focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus"
          >
            Edit Journal
          </button>
          <button
            type="button"
            onClick={() => setShowAuditDrawer(true)}
            className="rounded-md px-4 py-2 text-sm text-text-secondary hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus"
          >
            History ({auditCount})
          </button>
        </footer>
      )}

      {/* Empty-state footer is hidden per spec */}

      {/* Audit history drawer */}
      <AuditHistoryDrawer
        tradeId={trade.id}
        isOpen={showAuditDrawer}
        onClose={() => setShowAuditDrawer(false)}
      />
    </div>
  )
}
