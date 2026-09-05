import { apiClient } from '@/lib/api-client'
import type { Account, CreateAccountBody, UpdateAccountBody } from './types'

export const accountsApi = {
  list: () => apiClient.get<Account[]>('/v1/accounts'),
  create: (body: CreateAccountBody) => apiClient.post<Account>('/v1/accounts', body),
  update: (id: string, body: UpdateAccountBody) =>
    apiClient.patch<Account>(`/v1/accounts/${id}`, body),
  deactivate: (id: string) => apiClient.delete<void>(`/v1/accounts/${id}`),
}
