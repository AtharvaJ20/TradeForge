import { apiClient } from '@/lib/api-client'
import {
  JournalEntrySchema,
  AuditHistorySchema,
  PresignSchema,
  AttachmentConfirmSchema,
} from './schemas'
import type { JournalEntry, JournalEntryWrite, AuditEntry, PresignResult, AttachmentConfirm } from './types'

export async function fetchJournalEntry(tradeId: string): Promise<JournalEntry> {
  const raw = await apiClient.get(`/v1/journal/trades/${tradeId}`)
  return JournalEntrySchema.parse(raw)
}

export async function upsertJournalEntry(
  tradeId: string,
  data: JournalEntryWrite,
): Promise<JournalEntry> {
  const raw = await apiClient.put(`/v1/journal/trades/${tradeId}`, data)
  return JournalEntrySchema.parse(raw)
}

export async function fetchAuditHistory(tradeId: string): Promise<AuditEntry[]> {
  const raw = await apiClient.get(`/v1/journal/trades/${tradeId}/audit`)
  return AuditHistorySchema.parse(raw)
}

export interface PresignRequest {
  filename: string
  content_type: string
  byte_size: number
  capture_moment: string
  caption?: string | null
}

export async function presignAttachment(
  tradeId: string,
  req: PresignRequest,
): Promise<PresignResult> {
  const raw = await apiClient.post(`/v1/journal/trades/${tradeId}/attachments/presign`, req)
  return PresignSchema.parse(raw)
}

export async function confirmAttachment(
  tradeId: string,
  attachmentId: string,
): Promise<AttachmentConfirm> {
  const raw = await apiClient.post(
    `/v1/journal/trades/${tradeId}/attachments/${attachmentId}/confirm`,
  )
  return AttachmentConfirmSchema.parse(raw)
}

export async function deleteAttachment(tradeId: string, attachmentId: string): Promise<void> {
  await apiClient.delete(`/v1/journal/trades/${tradeId}/attachments/${attachmentId}`)
}

/**
 * Upload a file directly to S3 via a pre-signed PUT URL using XHR,
 * so we can track progress. Returns a cleanup function (abort).
 */
export function s3Upload(
  uploadUrl: string,
  file: File,
  onProgress: (pct: number) => void,
  onComplete: () => void,
  onError: (msg: string) => void,
): () => void {
  const xhr = new XMLHttpRequest()
  xhr.open('PUT', uploadUrl)
  xhr.setRequestHeader('Content-Type', file.type)

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
  }

  xhr.onload = () => {
    if (xhr.status === 200 || xhr.status === 204) {
      onComplete()
    } else {
      onError(`Upload failed (HTTP ${xhr.status})`)
    }
  }

  xhr.onerror = () => onError('Upload failed. Check your connection.')
  xhr.onabort = () => { /* cancelled by user — no error needed */ }

  xhr.send(file)
  return () => xhr.abort()
}
