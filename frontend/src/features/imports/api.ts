import { ApiError } from '@/lib/api-client'
import { apiClient } from '@/lib/api-client'
import type { ImportRecordOut, ImportSummaryOut } from './types'

const API_BASE = import.meta.env['VITE_API_BASE_URL'] ?? 'http://localhost:8000'

async function uploadFormData(path: string, body: FormData): Promise<ImportSummaryOut> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    body,
    // No Content-Type header — browser sets multipart/form-data with boundary automatically
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const b = (await res.json()) as { detail?: string }
      if (b.detail) detail = b.detail
    } catch {
      // non-JSON error body; keep default
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<ImportSummaryOut>
}

export const importsApi = {
  upload: (accountId: string, body: FormData) =>
    uploadFormData(`/v1/accounts/${accountId}/import`, body),

  list: (accountId: string) =>
    apiClient.get<ImportRecordOut[]>(`/v1/imports?account_id=${accountId}`),
}
