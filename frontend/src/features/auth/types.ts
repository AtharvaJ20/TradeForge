export interface User {
  id: string
  email: string
  display_name: string | null
  time_zone: string
  base_currency: string
  is_email_verified: boolean
  is_admin: boolean
  created_at: string
}

export interface UpdateProfileBody {
  display_name?: string | null
  time_zone?: string
  base_currency?: string
}
