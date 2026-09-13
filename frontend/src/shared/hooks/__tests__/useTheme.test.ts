import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// ---------------------------------------------------------------------------
// Environment setup — jsdom does not implement matchMedia
// ---------------------------------------------------------------------------

function setupMatchMedia(prefersDark: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn((query: string) => ({
      matches: prefersDark && query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  setupMatchMedia(false)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useTheme', () => {
  it('reads tf-theme from localStorage on mount', async () => {
    localStorage.setItem('tf-theme', 'dark')
    const { useTheme } = await import('../useTheme')
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('dark')
  })

  it('writes to localStorage and applies data-theme on toggle', async () => {
    localStorage.setItem('tf-theme', 'light')
    const { useTheme } = await import('../useTheme')
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('light')

    act(() => {
      result.current.toggle()
    })

    expect(result.current.theme).toBe('dark')
    expect(localStorage.getItem('tf-theme')).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('falls back to prefers-color-scheme: dark when no stored value', async () => {
    setupMatchMedia(true)
    const { useTheme } = await import('../useTheme')
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('dark')
  })

  it('applies data-theme attribute to <html> on mount', async () => {
    localStorage.setItem('tf-theme', 'light')
    const { useTheme } = await import('../useTheme')
    renderHook(() => useTheme())
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })
})
