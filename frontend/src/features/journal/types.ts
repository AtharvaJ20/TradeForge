import type { z } from 'zod'
import type {
  JournalEntrySchema,
  AttachmentSchema,
  PnlSnapshotSchema,
  AuditEntrySchema,
  PresignSchema,
  AttachmentConfirmSchema,
} from './schemas'

export type PnlStatus = 'PENDING_STOP' | 'PENDING_CALCULATION' | 'AVAILABLE'
export type AttachmentStatus = 'PENDING' | 'CONFIRMED' | 'EXPIRED' | 'REJECTED'
export type CaptureMoment = 'AT_ENTRY' | 'DURING_TRADE' | 'AT_EXIT' | 'POST_REVIEW'
export type EmotionType =
  | 'CALM'
  | 'CONFIDENT'
  | 'ANXIOUS'
  | 'FEARFUL'
  | 'GREEDY'
  | 'FRUSTRATED'
  | 'EUPHORIC'
  | 'BORED'
  | 'DISTRACTED'
  | 'NEUTRAL'
export type MistakeType =
  | 'FOMO_ENTRY'
  | 'FOMO_EXIT'
  | 'OVERSIZED_POSITION'
  | 'NO_STOP_DEFINED'
  | 'MOVED_STOP_WIDER'
  | 'CUT_WINNER_EARLY'
  | 'HELD_THROUGH_STOP'
  | 'REVENGE_TRADE'
  | 'AVERAGING_DOWN'
  | 'ENTRY_TOO_EARLY'
  | 'ENTRY_TOO_LATE'
  | 'IGNORED_SIGNAL'
  | 'DISTRACTED'

export type TradeType = 'MIS' | 'CNC' | 'CNC_SAME_DAY' | 'NRML_FUT' | 'NRML_OPT'
export type Direction = 'LONG' | 'SHORT'

export type PnlSnapshot = z.infer<typeof PnlSnapshotSchema>
export type AttachmentView = z.infer<typeof AttachmentSchema>
export type JournalEntry = z.infer<typeof JournalEntrySchema>
export type AuditEntry = z.infer<typeof AuditEntrySchema>
export type PresignResult = z.infer<typeof PresignSchema>
export type AttachmentConfirm = z.infer<typeof AttachmentConfirmSchema>

/** Minimal trade fields needed to render the journal panel. */
export interface TradeForJournal {
  id: string
  symbol: string
  exchange: string
  tradeDate: string       // ISO 8601 date
  firstFillAt: string     // ISO 8601 datetime
  direction: Direction
  tradeType: TradeType
  averageEntry: string | null
  totalEntryQuantity: string
}

/** Fields the user can write on a journal entry. Matches JournalEntryRequest on the backend. */
export interface JournalEntryWrite {
  planned_entry?: string | null
  planned_stop?: string | null
  planned_target?: string | null
  setup_name?: string | null
  notes?: string | null
  discipline_score?: number | null
  mistakes?: string[] | null
  emotion_before?: string | null
  emotion_during?: string | null
  emotion_after?: string | null
  change_reason?: string | null
}

/** Grouped audit change card (5-minute proximity grouping per spec §7.3). */
export interface AuditGroup {
  groupedAt: string               // ISO string of the first entry in the group
  entries: AuditEntry[]
}
