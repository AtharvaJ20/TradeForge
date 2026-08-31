import { useQuery } from '@tanstack/react-query'
import { fetchAuditHistory } from '../api'
import { journalKeys } from './useJournalEntry'

export function useAuditHistory(tradeId: string, enabled: boolean) {
  return useQuery({
    queryKey: journalKeys.audit(tradeId),
    queryFn: () => fetchAuditHistory(tradeId),
    enabled,
    staleTime: 0, // always refetch when drawer opens
  })
}
