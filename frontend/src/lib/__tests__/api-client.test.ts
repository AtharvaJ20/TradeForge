import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../__tests__/msw/server'
import { apiClient, ApiError } from '../api-client'

// ---------------------------------------------------------------------------
// DEF-J1-001 regression: FastAPI 422 detail is an array, not a string
// ---------------------------------------------------------------------------

describe('apiClient — error detail normalisation', () => {
  it('extracts msg from FastAPI 422 validation error array', async () => {
    server.use(
      http.post('http://localhost:8000/v1/auth/register', () =>
        new HttpResponse(
          JSON.stringify({
            detail: [
              {
                type: 'value_error',
                loc: ['body', 'password'],
                msg: 'Password must be at least 8 characters.',
                input: 'abc',
                ctx: {},
              },
            ],
          }),
          { status: 422, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    await expect(
      apiClient.post('/v1/auth/register', { email: 'a@b.com', password: 'abc' }),
    ).rejects.toSatisfy((err: unknown) => {
      if (!(err instanceof ApiError)) return false
      return err.status === 422 && err.detail === 'Password must be at least 8 characters.'
    })
  })

  it('uses string detail directly when backend returns a plain string', async () => {
    server.use(
      http.post('http://localhost:8000/v1/auth/register', () =>
        new HttpResponse(JSON.stringify({ detail: 'RATE_LIMITED' }), {
          status: 429,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    await expect(
      apiClient.post('/v1/auth/register', { email: 'a@b.com', password: 'Password1!' }),
    ).rejects.toSatisfy((err: unknown) => {
      if (!(err instanceof ApiError)) return false
      return err.status === 429 && err.detail === 'RATE_LIMITED'
    })
  })

  it('falls back to HTTP status when detail is absent', async () => {
    server.use(
      http.post('http://localhost:8000/v1/auth/register', () =>
        new HttpResponse(JSON.stringify({}), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    await expect(
      apiClient.post('/v1/auth/register', { email: 'a@b.com', password: 'Password1!' }),
    ).rejects.toSatisfy((err: unknown) => {
      if (!(err instanceof ApiError)) return false
      return err.status === 500 && err.detail === 'HTTP 500'
    })
  })
})
