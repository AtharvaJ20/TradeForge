import { z } from 'zod'

// FastAPI / Pydantic v2 serialises Decimal as string in JSON mode.
const decimalString = z.string().nullable()

export const PnlStatusSchema = z.enum(['PENDING_STOP', 'PENDING_CALCULATION', 'AVAILABLE'])

export const AttachmentStatusSchema = z.enum(['PENDING', 'CONFIRMED', 'EXPIRED', 'REJECTED'])

export const CaptureMomentSchema = z.enum([
  'AT_ENTRY',
  'DURING_TRADE',
  'AT_EXIT',
  'POST_REVIEW',
])

export const EmotionTypeSchema = z.enum([
  'CALM',
  'CONFIDENT',
  'ANXIOUS',
  'FEARFUL',
  'GREEDY',
  'FRUSTRATED',
  'EUPHORIC',
  'BORED',
  'DISTRACTED',
  'NEUTRAL',
])

export const MistakeTypeSchema = z.enum([
  'FOMO_ENTRY',
  'FOMO_EXIT',
  'OVERSIZED_POSITION',
  'NO_STOP_DEFINED',
  'MOVED_STOP_WIDER',
  'CUT_WINNER_EARLY',
  'HELD_THROUGH_STOP',
  'REVENGE_TRADE',
  'AVERAGING_DOWN',
  'ENTRY_TOO_EARLY',
  'ENTRY_TOO_LATE',
  'IGNORED_SIGNAL',
  'DISTRACTED',
])

export const PnlSnapshotSchema = z.object({
  status: PnlStatusSchema,
  net_pnl: decimalString,
  gross_pnl: decimalString,
  total_charges: decimalString,
  r_multiple: decimalString,
})

export const AttachmentSchema = z.object({
  id: z.string().uuid(),
  filename: z.string(),
  content_type: z.string(),
  byte_size: z.number().int(),
  capture_moment: CaptureMomentSchema,
  caption: z.string().nullable(),
  status: AttachmentStatusSchema,
  download_url: z.string().nullable(),
  confirmed_at: z.string().nullable(),
  created_at: z.string(),
})

export const JournalEntrySchema = z.object({
  id: z.string().uuid(),
  trade_id: z.string().uuid(),
  planned_entry: decimalString,
  planned_stop: decimalString,
  planned_target: decimalString,
  planned_risk_amount: decimalString,
  setup_name: z.string().nullable(),
  notes: z.string().nullable(),
  discipline_score: z.number().int().nullable(),
  mistakes: z.array(z.string()),
  emotion_before: z.string().nullable(),
  emotion_during: z.string().nullable(),
  emotion_after: z.string().nullable(),
  pnl: PnlSnapshotSchema,
  attachments: z.array(AttachmentSchema),
  created_at: z.string(),
  updated_at: z.string(),
})

export const AuditEntrySchema = z.object({
  id: z.string(),
  field_name: z.string(),
  previous_value: z.string().nullable(),
  new_value: z.string().nullable(),
  change_reason: z.string().nullable(),
  changed_at: z.string(),
})

export const AuditHistorySchema = z.array(AuditEntrySchema)

export const PresignSchema = z.object({
  attachment_id: z.string().uuid(),
  upload_url: z.string(),
  s3_key: z.string(),
  expires_in_seconds: z.number().int(),
})

export const AttachmentConfirmSchema = z.object({
  id: z.string().uuid(),
  filename: z.string(),
  content_type: z.string(),
  byte_size: z.number().int(),
  status: AttachmentStatusSchema,
  download_url: z.string().nullable(),
  confirmed_at: z.string().nullable(),
})
