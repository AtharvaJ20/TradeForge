import { useCallback, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { presignAttachment, confirmAttachment, s3Upload } from '../api'
import { journalKeys } from './useJournalEntry'
import type { JournalEntry, CaptureMoment, AttachmentView } from '../types'
import { ApiError } from '@/lib/api-client'

export type UploadState =
  | { stage: 'IDLE' }
  | { stage: 'FILE_SELECTED'; file: File }
  | { stage: 'VALIDATION_ERROR'; message: string }
  | { stage: 'UPLOADING'; file: File; progress: number }
  | { stage: 'UPLOAD_ERROR'; file: File; message: string }
  | { stage: 'CONFIRMING'; file: File }
  | { stage: 'SUCCESS'; attachment: AttachmentView }

interface UseAttachmentUploadOptions {
  tradeId: string
  /** Injected in tests to replace the XHR upload step. */
  uploadFn?: typeof s3Upload
}

export function useAttachmentUpload({ tradeId, uploadFn = s3Upload }: UseAttachmentUploadOptions) {
  const [state, setState] = useState<UploadState>({ stage: 'IDLE' })
  const queryClient = useQueryClient()
  const abortRef = useRef<(() => void) | null>(null)

  const selectFile = useCallback((file: File) => {
    setState({ stage: 'FILE_SELECTED', file })
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.()
    abortRef.current = null
    setState({ stage: 'IDLE' })
  }, [])

  const upload = useCallback(
    async (
      file: File,
      captureMoment: CaptureMoment,
      caption: string | null,
    ) => {
      try {
        const presign = await presignAttachment(tradeId, {
          filename: file.name,
          content_type: file.type,
          byte_size: file.size,
          capture_moment: captureMoment,
          caption,
        })

        setState({ stage: 'UPLOADING', file, progress: 0 })

        await new Promise<void>((resolve, reject) => {
          abortRef.current = uploadFn(
            presign.upload_url,
            file,
            (pct) => setState({ stage: 'UPLOADING', file, progress: pct }),
            resolve,
            (msg) => reject(new Error(msg)),
          )
        })

        abortRef.current = null
        setState({ stage: 'CONFIRMING', file })

        const confirmed = await confirmAttachment(tradeId, presign.attachment_id)

        // Convert to AttachmentView shape for the cache update
        const newAttachment: AttachmentView = {
          id: confirmed.id,
          filename: confirmed.filename,
          content_type: confirmed.content_type,
          byte_size: confirmed.byte_size,
          capture_moment: captureMoment,
          caption,
          status: confirmed.status,
          download_url: confirmed.download_url,
          confirmed_at: confirmed.confirmed_at,
          created_at: new Date().toISOString(),
        }

        queryClient.setQueryData<JournalEntry>(journalKeys.entry(tradeId), (old) => {
          if (!old) return old
          return { ...old, attachments: [...old.attachments, newAttachment] }
        })

        setState({ stage: 'SUCCESS', attachment: newAttachment })
        return newAttachment
      } catch (err) {
        const message =
          err instanceof ApiError ? err.detail
          : err instanceof Error ? err.message
          : 'Upload failed.'

        if (state.stage === 'UPLOADING' || state.stage === 'FILE_SELECTED') {
          const file = state.stage === 'UPLOADING' ? state.file
            : state.stage === 'FILE_SELECTED' ? state.file
            : null
          if (file) {
            setState({ stage: 'UPLOAD_ERROR', file, message })
          }
        } else {
          setState({ stage: 'UPLOAD_ERROR', file: new File([], ''), message })
        }
        return null
      }
    },
    [tradeId, uploadFn, queryClient, state],
  )

  const cancel = useCallback(() => {
    abortRef.current?.()
    abortRef.current = null
    setState({ stage: 'IDLE' })
  }, [])

  return { state, selectFile, upload, reset, cancel }
}
