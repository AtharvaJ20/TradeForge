import { useMutation, useQueryClient } from '@tanstack/react-query'
import { upsertJournalEntry } from '../api'
import { journalKeys } from './useJournalEntry'
import type { JournalEntryWrite } from '../types'

export function useUpsertJournalEntry(tradeId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: JournalEntryWrite) => upsertJournalEntry(tradeId, data),
    onSuccess: (updated) => {
      queryClient.setQueryData(journalKeys.entry(tradeId), updated)
    },
  })
}
