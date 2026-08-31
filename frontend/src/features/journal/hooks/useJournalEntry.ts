import { useQuery } from '@tanstack/react-query'
import { fetchJournalEntry } from '../api'
import { ApiError } from '@/lib/api-client'

export const journalKeys = {
  entry: (tradeId: string) => ['journal', 'entry', tradeId] as const,
  audit: (tradeId: string) => ['journal', 'audit', tradeId] as const,
}

export function useJournalEntry(tradeId: string) {
  return useQuery({
    queryKey: journalKeys.entry(tradeId),
    // 404 = no entry yet; return null so isError stays false in the panel
    queryFn: async () => {
      try {
        return await fetchJournalEntry(tradeId)
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null
        throw e
      }
    },
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) return false
      return failureCount < 1
    },
  })
}
