import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteAttachment } from '../api'
import { journalKeys } from './useJournalEntry'
import type { JournalEntry } from '../types'
import { ApiError } from '@/lib/api-client'

export function useDeleteAttachment(tradeId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (attachmentId: string) => deleteAttachment(tradeId, attachmentId),
    onMutate: async (attachmentId: string) => {
      await queryClient.cancelQueries({ queryKey: journalKeys.entry(tradeId) })
      const previous = queryClient.getQueryData<JournalEntry>(journalKeys.entry(tradeId))
      queryClient.setQueryData<JournalEntry>(journalKeys.entry(tradeId), (old) => {
        if (!old) return old
        return {
          ...old,
          attachments: old.attachments.filter((a) => a.id !== attachmentId),
        }
      })
      return { previous }
    },
    onError: (err, _attachmentId, context) => {
      // On 404 the attachment is already gone — don't roll back
      if (err instanceof ApiError && err.status === 404) return
      if (context?.previous) {
        queryClient.setQueryData(journalKeys.entry(tradeId), context.previous)
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: journalKeys.entry(tradeId) })
    },
  })
}
