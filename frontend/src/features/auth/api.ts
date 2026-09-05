import { apiClient } from '@/lib/api-client'
import type { User } from './types'

export const authApi = {
  me: () => apiClient.get<User>('/v1/auth/me'),
  login: (email: string, password: string) =>
    apiClient.post<User>('/v1/auth/login', { email, password }),
  logout: () => apiClient.post<{ message: string }>('/v1/auth/logout'),
  register: (email: string, password: string) =>
    apiClient.post<{ message: string }>('/v1/auth/register', { email, password }),
  verifyEmail: (token: string) =>
    apiClient.post<{ message: string }>('/v1/auth/verify-email', { token }),
  requestPasswordReset: (email: string) =>
    apiClient.post<{ message: string }>('/v1/auth/password-reset/request', { email }),
  confirmPasswordReset: (token: string, new_password: string) =>
    apiClient.post<{ message: string }>('/v1/auth/password-reset/confirm', {
      token,
      new_password,
    }),
}
