import { useQuery } from '@tanstack/react-query'
import { fetchFilterAccounts, fetchFilterBrokers, fetchFilterSetups } from '../api'
import type { AccountDimension } from '../types'

export interface FilterDimensions {
  accounts: AccountDimension[]
  setups: string[]
  brokers: string[]
  isLoading: boolean
  accountsError: boolean
  setupsError: boolean
  brokersError: boolean
}

export const filterDimensionKeys = {
  accounts: ['analytics', 'filters', 'accounts'] as const,
  setups: ['analytics', 'filters', 'setups'] as const,
  brokers: ['analytics', 'filters', 'brokers'] as const,
}

export function useFilterDimensions(): FilterDimensions {
  const accountsQuery = useQuery({
    queryKey: filterDimensionKeys.accounts,
    queryFn: fetchFilterAccounts,
    retry: 1,
  })

  const setupsQuery = useQuery({
    queryKey: filterDimensionKeys.setups,
    queryFn: fetchFilterSetups,
    retry: 1,
  })

  const brokersQuery = useQuery({
    queryKey: filterDimensionKeys.brokers,
    queryFn: fetchFilterBrokers,
    retry: 1,
  })

  return {
    accounts: accountsQuery.data ?? [],
    setups: setupsQuery.data ?? [],
    brokers: brokersQuery.data ?? [],
    isLoading:
      accountsQuery.isLoading || setupsQuery.isLoading || brokersQuery.isLoading,
    accountsError: accountsQuery.isError,
    setupsError: setupsQuery.isError,
    brokersError: brokersQuery.isError,
  }
}
