import { z } from 'zod'

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  is_email_verified: z.boolean(),
  is_admin: z.boolean(),
})

export const MessageSchema = z.object({ message: z.string() })
