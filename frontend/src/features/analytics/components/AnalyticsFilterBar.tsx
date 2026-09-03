import type { AnalyticsFilterParams } from '../types'

const DIRECTIONS = ['LONG', 'SHORT'] as const
const TRADE_TYPES = ['INTRADAY', 'SWING', 'POSITIONAL'] as const
const INSTRUMENT_TYPES = ['FUT', 'OPT', 'EQ', 'CFD'] as const
const EXCHANGE_SEGMENTS = ['NSE', 'BSE', 'NFO', 'BFO', 'MCX', 'CDS'] as const

type ArrayKey = 'directions' | 'trade_types' | 'instrument_types' | 'exchange_segments'

function toggleArrayParam(
  params: AnalyticsFilterParams,
  key: ArrayKey,
  val: string,
): AnalyticsFilterParams {
  const arr = params[key] ?? []
  const next = arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val]
  const updated = { ...params }
  if (next.length === 0) {
    delete updated[key]
  } else {
    updated[key] = next
  }
  return updated
}

interface CheckboxGroupProps {
  legend: string
  options: readonly string[]
  selected: string[] | undefined
  onToggle: (val: string) => void
}

function CheckboxGroup({ legend, options, selected, onToggle }: CheckboxGroupProps) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-text-secondary">
        {legend}
      </legend>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {options.map(opt => (
          <label
            key={opt}
            className="flex cursor-pointer items-center gap-1.5 text-sm text-text-primary"
          >
            <input
              type="checkbox"
              checked={(selected ?? []).includes(opt)}
              onChange={() => onToggle(opt)}
              className="h-3.5 w-3.5 rounded border-border"
            />
            {opt}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

export interface AnalyticsFilterBarProps {
  value: AnalyticsFilterParams
  onChange: (params: AnalyticsFilterParams) => void
}

export function AnalyticsFilterBar({ value, onChange }: AnalyticsFilterBarProps) {
  function toggleKey(key: ArrayKey, val: string) {
    onChange(toggleArrayParam(value, key, val))
  }

  function handleDateChange(key: 'date_from' | 'date_to', val: string) {
    const updated = { ...value }
    if (val) {
      updated[key] = val
    } else {
      delete updated[key]
    }
    onChange(updated)
  }

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-4"
      aria-label="Analytics filters"
    >
      <div className="flex flex-wrap items-start gap-x-6 gap-y-4">
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="filter-date-from"
            className="text-xs font-semibold uppercase tracking-wider text-text-secondary"
          >
            Date from
          </label>
          <input
            id="filter-date-from"
            type="date"
            value={value.date_from ?? ''}
            onChange={e => handleDateChange('date_from', e.target.value)}
            className="rounded border border-border bg-surface-subtle px-2 py-1 text-sm text-text-primary"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="filter-date-to"
            className="text-xs font-semibold uppercase tracking-wider text-text-secondary"
          >
            Date to
          </label>
          <input
            id="filter-date-to"
            type="date"
            value={value.date_to ?? ''}
            onChange={e => handleDateChange('date_to', e.target.value)}
            className="rounded border border-border bg-surface-subtle px-2 py-1 text-sm text-text-primary"
          />
        </div>

        <CheckboxGroup
          legend="Direction"
          options={DIRECTIONS}
          selected={value.directions}
          onToggle={val => toggleKey('directions', val)}
        />

        <CheckboxGroup
          legend="Trade type"
          options={TRADE_TYPES}
          selected={value.trade_types}
          onToggle={val => toggleKey('trade_types', val)}
        />

        <CheckboxGroup
          legend="Instrument"
          options={INSTRUMENT_TYPES}
          selected={value.instrument_types}
          onToggle={val => toggleKey('instrument_types', val)}
        />

        <CheckboxGroup
          legend="Segment"
          options={EXCHANGE_SEGMENTS}
          selected={value.exchange_segments}
          onToggle={val => toggleKey('exchange_segments', val)}
        />
      </div>

      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={() => onChange({})}
          className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:border-text-secondary hover:text-text-primary"
        >
          Clear all
        </button>
      </div>
    </section>
  )
}
