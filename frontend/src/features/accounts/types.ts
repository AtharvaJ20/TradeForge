export interface Account {
  id: string
  user_id: string
  broker: string
  display_name: string
  account_type: string
  base_currency: string
  status: 'ACTIVE' | 'INACTIVE'
  created_at: string
  updated_at: string
}

export interface CreateAccountBody {
  broker: string
  display_name: string
  account_type: string
  base_currency: string
}

export interface UpdateAccountBody {
  display_name?: string
  account_type?: string
}
