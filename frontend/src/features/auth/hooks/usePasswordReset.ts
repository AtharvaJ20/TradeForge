import { useMutation } from '@tanstack/react-query'
import { authApi } from '../api'

export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: (email: string) => authApi.requestPasswordReset(email),
  })
}

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: ({ token, newPassword }: { token: string; newPassword: string }) =>
      authApi.confirmPasswordReset(token, newPassword),
  })
}
