import { useRef, useState } from 'react'
import { formatBytes } from '@/lib/utils'
import { useAttachmentUpload } from '../hooks/useAttachmentUpload'
import type { CaptureMoment } from '../types'

const CAPTURE_MOMENTS: { value: CaptureMoment; label: string }[] = [
  { value: 'AT_ENTRY', label: 'At entry' },
  { value: 'DURING_TRADE', label: 'During trade' },
  { value: 'AT_EXIT', label: 'At exit' },
  { value: 'POST_REVIEW', label: 'Post review' },
]

const MAX_BYTES = 10 * 1024 * 1024 // 10 MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf']

interface AttachmentUploaderProps {
  tradeId: string
  onSuccess?: () => void
}

/** C-10 AttachmentUploader — file picker + XHR upload state machine. */
export function AttachmentUploader({ tradeId, onSuccess }: AttachmentUploaderProps) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [captureMoment, setCaptureMoment] = useState<CaptureMoment>('AT_EXIT')
  const [caption, setCaption] = useState('')
  const { state, selectFile, upload, reset } = useAttachmentUpload({ tradeId })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Client-side validation before presign
    if (!ALLOWED_TYPES.includes(file.type)) {
      selectFile(file) // triggers VALIDATION_ERROR via useAttachmentUpload internal logic
      return
    }
    if (file.size > MAX_BYTES) {
      selectFile(file)
      return
    }
    selectFile(file)
  }

  const handleUpload = async () => {
    if (state.stage !== 'FILE_SELECTED') return
    const result = await upload(state.file, captureMoment, caption.trim() || null)
    if (result) {
      setCaption('')
      if (fileRef.current) fileRef.current.value = ''
      onSuccess?.()
    }
  }

  const isUploading = state.stage === 'UPLOADING' || state.stage === 'CONFIRMING'

  return (
    <section aria-label="Upload attachment" className="space-y-3 rounded-md border border-border p-4">
      <h3 className="text-sm font-semibold text-text-primary">Add Attachment</h3>

      {state.stage === 'IDLE' || state.stage === 'FILE_SELECTED' || state.stage === 'VALIDATION_ERROR' ? (
        <>
          {/* File picker */}
          <div>
            <label htmlFor="attachment-file" className="sr-only">
              Choose file
            </label>
            <input
              ref={fileRef}
              id="attachment-file"
              type="file"
              accept={ALLOWED_TYPES.join(',')}
              onChange={handleFileChange}
              className="text-sm text-text-secondary file:mr-3 file:cursor-pointer file:rounded-md file:border file:border-border file:bg-surface-subtle file:px-3 file:py-1 file:text-xs file:font-medium file:text-text-primary"
            />
          </div>

          {state.stage === 'VALIDATION_ERROR' && (
            <p role="alert" className="text-xs text-danger-emphasis">
              {state.message}
            </p>
          )}

          {state.stage === 'FILE_SELECTED' && (
            <>
              <p className="text-xs text-text-secondary">
                {state.file.name} — {formatBytes(state.file.size)}
              </p>

              {/* Capture moment */}
              <div>
                <label htmlFor="capture-moment" className="text-xs font-medium text-text-primary">
                  Capture moment
                </label>
                <select
                  id="capture-moment"
                  value={captureMoment}
                  onChange={(e) => setCaptureMoment(e.target.value as CaptureMoment)}
                  className="mt-1 w-full rounded-md border border-border bg-surface-neutral px-3 py-2 text-sm text-text-primary focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  {CAPTURE_MOMENTS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Caption */}
              <div>
                <label htmlFor="attachment-caption" className="text-xs font-medium text-text-primary">
                  Caption (optional)
                </label>
                <input
                  id="attachment-caption"
                  type="text"
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  maxLength={255}
                  className="mt-1 w-full rounded-md border border-border bg-surface-neutral px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="e.g. Entry signal chart"
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleUpload}
                  className="flex-1 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-50"
                >
                  Upload
                </button>
                <button
                  type="button"
                  onClick={reset}
                  className="rounded-md border border-border px-3 py-2 text-sm text-text-secondary hover:text-text-primary"
                >
                  Cancel
                </button>
              </div>
            </>
          )}
        </>
      ) : null}

      {isUploading && (
        <div role="status" aria-live="polite" className="space-y-2">
          <p className="text-sm text-text-primary">
            {state.stage === 'CONFIRMING' ? 'Confirming…' : `Uploading…`}
          </p>
          {state.stage === 'UPLOADING' && (
            <div className="h-2 overflow-hidden rounded-full bg-surface-subtle">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${state.progress}%` }}
                role="progressbar"
                aria-valuenow={state.progress}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Upload progress"
              />
            </div>
          )}
        </div>
      )}

      {state.stage === 'UPLOAD_ERROR' && (
        <div role="alert" className="space-y-2">
          <p className="text-sm text-danger-emphasis">{state.message}</p>
          <button
            type="button"
            onClick={reset}
            className="text-xs text-text-secondary underline-offset-2 hover:underline"
          >
            Try again
          </button>
        </div>
      )}

      {state.stage === 'SUCCESS' && (
        <div role="status" className="flex items-center gap-2 text-sm text-success-emphasis">
          <span aria-hidden="true">✓</span>
          <span>Uploaded: {state.attachment.filename}</span>
          <button
            type="button"
            onClick={reset}
            className="ml-auto text-xs text-text-secondary underline-offset-2 hover:underline"
          >
            Add another
          </button>
        </div>
      )}
    </section>
  )
}
