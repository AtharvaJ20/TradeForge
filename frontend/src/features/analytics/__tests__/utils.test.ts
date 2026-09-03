import { describe, it, expect } from 'vitest'
import { countActiveFilterDimensions } from '../utils'

describe('countActiveFilterDimensions', () => {
  it('returns 0 for empty params', () => {
    expect(countActiveFilterDimensions({})).toBe(0)
  })

  it('counts date_from as 1 dimension', () => {
    expect(countActiveFilterDimensions({ date_from: '2026-01-01' })).toBe(1)
  })

  it('counts date_to as 1 dimension (not a second)', () => {
    expect(countActiveFilterDimensions({ date_to: '2026-12-31' })).toBe(1)
  })

  it('counts both date_from and date_to as 1 shared dimension', () => {
    expect(
      countActiveFilterDimensions({ date_from: '2026-01-01', date_to: '2026-12-31' }),
    ).toBe(1)
  })

  it('counts each non-empty array dimension as 1', () => {
    expect(countActiveFilterDimensions({ directions: ['LONG'] })).toBe(1)
    expect(countActiveFilterDimensions({ trade_types: ['SWING'] })).toBe(1)
    expect(countActiveFilterDimensions({ instrument_types: ['FUT'] })).toBe(1)
    expect(countActiveFilterDimensions({ exchange_segments: ['NSE'] })).toBe(1)
    expect(countActiveFilterDimensions({ account_ids: ['some-uuid'] })).toBe(1)
    expect(countActiveFilterDimensions({ setup_names: ['Breakout'] })).toBe(1)
    expect(countActiveFilterDimensions({ brokers: ['ZERODHA'] })).toBe(1)
  })

  it('counts multiple selected values within one dimension as 1', () => {
    expect(countActiveFilterDimensions({ directions: ['LONG', 'SHORT'] })).toBe(1)
    expect(countActiveFilterDimensions({ account_ids: ['uuid-1', 'uuid-2'] })).toBe(1)
  })

  it('counts multiple active dimensions independently', () => {
    expect(
      countActiveFilterDimensions({
        date_from: '2026-01-01',
        directions: ['LONG'],
        setup_names: ['Breakout'],
      }),
    ).toBe(3)
  })

  it('returns 8 for all dimensions active simultaneously', () => {
    expect(
      countActiveFilterDimensions({
        date_from: '2026-01-01',
        account_ids: ['uuid-1'],
        setup_names: ['Breakout'],
        brokers: ['ZERODHA'],
        directions: ['LONG'],
        trade_types: ['SWING'],
        instrument_types: ['FUT'],
        exchange_segments: ['NSE'],
      }),
    ).toBe(8)
  })

  it('does not count empty arrays', () => {
    expect(countActiveFilterDimensions({ directions: [] })).toBe(0)
    expect(countActiveFilterDimensions({ account_ids: [] })).toBe(0)
  })
})
