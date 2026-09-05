import { useMutation } from '@tanstack/react-query'
import { authApi } from '../api'

export function useRegister() {
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      authApi.register(email, password),
  })
}
