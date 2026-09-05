import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi } from '@/features/auth/api'
import { ApiError } from '@/lib/api-client'
import type { UpdateProfileBody } from '@/features/auth/types'

const TIMEZONE_OPTIONS = [
  'Asia/Kolkata',
  'Asia/Dubai',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Seoul',
  'Asia/Karachi',
  'Asia/Dhaka',
  'Asia/Bangkok',
  'Europe/London',
  'Europe/Berlin',
  'Europe/Paris',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'America/Toronto',
  'America/Sao_Paulo',
  'Australia/Sydney',
  'Pacific/Auckland',
  'UTC',
]

export function ProfileSection() {
  const queryClient = useQueryClient()

  const { data: profile, isLoading } = useQuery({
    queryKey: ['user-profile'],
    queryFn: authApi.getProfile,
  })

  const [displayName, setDisplayName] = useState('')
  const [timeZone, setTimeZone] = useState('Asia/Kolkata')
  const [baseCurrency] = useState('INR')
  const [clientError, setClientError] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    if (profile) {
      setDisplayName(profile.display_name ?? '')
      setTimeZone(profile.time_zone ?? 'Asia/Kolkata')
    }
  }, [profile])

  const mutation = useMutation({
    mutationFn: authApi.updateProfile,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['user-profile'] })
      setServerError(null)
      setSuccess(true)
    },
    onError: (err) => {
      setSuccess(false)
      if (err instanceof ApiError) {
        setServerError(err.detail)
      } else {
        setServerError('An unexpected error occurred')
      }
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setClientError(null)
    setServerError(null)
    setSuccess(false)

    if (displayName.trim() === '' && displayName !== '') {
      setClientError('Display name cannot be blank')
      return
    }
    if (displayName !== '' && displayName.trim() === '') {
      setClientError('Display name cannot be blank')
      return
    }

    const body: UpdateProfileBody = {
      time_zone: timeZone,
    }
    if (displayName.trim() !== '') {
      body.display_name = displayName.trim()
    } else if (displayName === '') {
      body.display_name = null
    }

    mutation.mutate(body)
  }

  if (isLoading) {
    return <div className="text-text-secondary text-sm">Loading profile…</div>
  }

  return (
    <section aria-label="Profile settings" className="max-w-md">
      <h2 className="text-base font-semibold text-text-primary mb-4">Profile</h2>

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="display-name" className="text-sm font-medium text-text-primary">
            Display Name
          </label>
          <input
            id="display-name"
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Your name"
            maxLength={100}
            className="rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
          {clientError && (
            <p role="alert" className="text-xs text-red-500">
              {clientError}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="time-zone" className="text-sm font-medium text-text-primary">
            Time Zone
          </label>
          <select
            id="time-zone"
            value={timeZone}
            onChange={(e) => setTimeZone(e.target.value)}
            className="rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            {TIMEZONE_OPTIONS.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="base-currency" className="text-sm font-medium text-text-primary">
            Base Currency
          </label>
          <select
            id="base-currency"
            value={baseCurrency}
            disabled
            className="rounded-lg border border-border bg-surface-subtle px-3 py-2 text-sm text-text-secondary focus:outline-none"
          >
            <option value="INR">INR</option>
          </select>
        </div>

        {serverError && (
          <p role="alert" className="text-sm text-red-500">
            {serverError === 'DISPLAY_NAME_BLANK'
              ? 'Display name cannot be blank'
              : serverError === 'INVALID_TIMEZONE'
                ? 'Invalid time zone'
                : serverError === 'UNSUPPORTED_CURRENCY'
                  ? 'Unsupported currency'
                  : serverError}
          </p>
        )}

        {success && (
          <p role="status" className="text-sm text-green-600">
            Profile updated successfully.
          </p>
        )}

        <button
          type="submit"
          disabled={mutation.isPending}
          className="self-start rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50"
        >
          {mutation.isPending ? 'Saving…' : 'Save changes'}
        </button>
      </form>
    </section>
  )
}
