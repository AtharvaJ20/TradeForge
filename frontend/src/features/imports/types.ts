// Response from POST /v1/accounts/{account_id}/import
export interface ImportSummaryOut {
  import_record_id: string
  fills_ingested: number
  fills_skipped: number
  row_errors: number
  trades_created: number
  trades_closed: number
  pnl_succeeded: number
  pnl_failed: number
  status: 'COMPLETE' | 'PARTIAL' | 'EMPTY' | 'FAILED'
}

// One row in the import history list
export interface ImportRecordOut {
  id: string
  account_id: string
  broker: string
  file_name: string | null
  row_count: number
  error_count: number
  status: 'COMPLETE' | 'PARTIAL' | 'EMPTY' | 'FAILED'
  imported_at: string
  created_at: string
}
