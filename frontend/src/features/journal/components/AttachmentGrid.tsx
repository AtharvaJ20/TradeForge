import { useState } from 'react'
import { formatBytes } from '@/lib/utils'
import { useDeleteAttachment } from '../hooks/useDeleteAttachment'
import type { AttachmentView } from '../types'

interface AttachmentGridProps {
  tradeId: string
  attachments: AttachmentView[]
}

/** 80×80 thumbnail grid with lightbox and context-menu delete. */
export function AttachmentGrid({ tradeId, attachments }: AttachmentGridProps) {
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; id: string } | null>(null)
  const { mutate: deleteAttachment, isPending } = useDeleteAttachment(tradeId)

  if (attachments.length === 0) return null

  const isImage = (contentType: string) => contentType.startsWith('image/')

  const closeMenu = () => setContextMenu(null)

  return (
    <>
      <div
        role="list"
        aria-label="Attachments"
        className="flex flex-wrap gap-2"
        onClick={closeMenu}
      >
        {attachments.map((att) => (
          <div
            key={att.id}
            role="listitem"
            className="group relative h-20 w-20 overflow-hidden rounded-md border border-border bg-surface-subtle"
          >
            {isImage(att.content_type) && att.download_url ? (
              <button
                type="button"
                aria-label={`View ${att.filename}`}
                onClick={(e) => {
                  e.stopPropagation()
                  setLightboxUrl(att.download_url)
                }}
                className="h-full w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus"
              >
                <img
                  src={att.download_url ?? undefined}
                  alt={att.filename}
                  className="h-full w-full object-cover"
                />
              </button>
            ) : (
              <div className="flex h-full w-full flex-col items-center justify-center gap-1 p-1 text-center">
                <span className="text-lg" aria-hidden="true">📎</span>
                <span className="truncate text-xs text-text-secondary">{att.filename}</span>
                <span className="text-xs text-text-tertiary">{formatBytes(att.byte_size)}</span>
              </div>
            )}

            {/* Context menu trigger */}
            <button
              type="button"
              aria-label={`Options for ${att.filename}`}
              onClick={(e) => {
                e.stopPropagation()
                setContextMenu({ x: e.clientX, y: e.clientY, id: att.id })
              }}
              className="absolute right-1 top-1 hidden rounded bg-black/50 px-1 py-0.5 text-xs text-white group-hover:flex group-focus-within:flex focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus"
            >
              ⋯
            </button>
          </div>
        ))}
      </div>

      {/* Context menu */}
      {contextMenu && (
        <div
          role="menu"
          aria-label="Attachment options"
          style={{ position: 'fixed', top: contextMenu.y, left: contextMenu.x, zIndex: 60 }}
          className="min-w-[140px] rounded-md border border-border bg-surface-base py-1 shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            disabled={isPending}
            onClick={() => {
              deleteAttachment(contextMenu.id)
              closeMenu()
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-danger-emphasis hover:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      )}

      {/* Lightbox */}
      {lightboxUrl && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Image preview"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
          onClick={() => setLightboxUrl(null)}
        >
          <button
            type="button"
            className="absolute right-4 top-4 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
            onClick={() => setLightboxUrl(null)}
            aria-label="Close preview"
          >
            ✕
          </button>
          <img
            src={lightboxUrl}
            alt="Attachment preview"
            className="max-h-[90vh] max-w-[90vw] rounded-md object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  )
}
