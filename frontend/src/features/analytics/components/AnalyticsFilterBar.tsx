import { useFilterDimensions } from '../hooks/useFilterDimensions'
import type { AccountDimension, AnalyticsFilterParams } from '../types'

// ---------------------------------------------------------------------------
// Static enumerations (decision D-1 — schema-level, not data-level)
// ---------------------------------------------------------------------------

const DIRECTIONS = ['LONG', 'SHORT'] as const
const TRADE_TYPES = ['INTRADAY', 'SWING', 'POSITIONAL'] as const
const INSTRUMENT_TYPES = ['FUT', 'OPT', 'EQ', 'CFD'] as const
const EXCHANGE_SEGMENTS = ['NSE', 'BSE', 'NFO', 'BFO', 'MCX', 'CDS'] as const

type ArrayKey =
  | 'directions'
  | 'trade_types'
  | 'instrument_types'
  | 'exchange_segments'
  | 'account_ids'
  | 'setup_names'
  | 'brokers'

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

// ---------------------------------------------------------------------------
// CheckboxGroup — options where value === label (static enumerations)
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// LabeledCheckboxGroup — options where stored value differs from display label
// Used for accounts (value = UUID, label = display name)
// ---------------------------------------------------------------------------

interface LabeledOption {
  value: string
  label: string
}

interface LabeledCheckboxGroupProps {
  legend: string
  options: LabeledOption[]
  selected: string[] | undefined
  onToggle: (val: string) => void
}

function LabeledCheckboxGroup({
  legend,
  options,
  selected,
  onToggle,
}: LabeledCheckboxGroupProps) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-text-secondary">
        {legend}
      </legend>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {options.map(opt => (
          <label
            key={opt.value}
            className="flex cursor-pointer items-center gap-1.5 text-sm text-text-primary"
          >
            <input
              type="checkbox"
              checked={(selected ?? []).includes(opt.value)}
              onChange={() => onToggle(opt.value)}
              className="h-3.5 w-3.5 rounded border-border"
            />
            {opt.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

// ---------------------------------------------------------------------------
// DimensionSkeleton — pulse placeholder while dynamic options load
// ---------------------------------------------------------------------------

function DimensionSkeleton({ legend }: { legend: string }) {
  return (
    <div className="min-w-0" aria-busy="true" aria-label={`Loading ${legend} options`}>
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-text-secondary">
        {legend}
      </p>
      <div className="flex gap-3">
        <div className="h-4 w-16 animate-pulse rounded bg-surface-subtle" />
        <div className="h-4 w-20 animate-pulse rounded bg-surface-subtle" />
        <div className="h-4 w-14 animate-pulse rounded bg-surface-subtle" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// DimensionError — inline non-blocking error when a dimension fetch fails
// ---------------------------------------------------------------------------

function DimensionError({ legend }: { legend: string }) {
  return (
    <div className="min-w-0">
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-text-secondary">
        {legend}
      </p>
      <p className="text-xs text-text-secondary" role="note">
        Unable to load options
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export interface AnalyticsFilterBarProps {
  value: AnalyticsFilterParams
  onChange: (params: AnalyticsFilterParams) => void
}

export function AnalyticsFilterBar({ value, onChange }: AnalyticsFilterBarProps) {
  const { accounts, setups, brokers, isLoading, accountsError, setupsError, brokersError } =
    useFilterDimensions()

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

  // Convert AccountDimension[] → LabeledOption[]
  const accountOptions: LabeledOption[] = accounts.map((a: AccountDimension) => ({
    value: a.id,
    label: a.label,
  }))

  // Convert string[] → LabeledOption[] (value = label)
  const setupOptions: LabeledOption[] = setups.map(s => ({ value: s, label: s }))
  const brokerOptions: LabeledOption[] = brokers.map(b => ({ value: b, label: b }))

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-4"
      aria-label="Analytics filters"
    >
      <div className="flex flex-wrap items-start gap-x-6 gap-y-4">
        {/* Date range — static */}
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

        {/* Static enumeration groups */}
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

        {/* Dynamic dimension groups — account, setup, broker */}
        {isLoading && !accountsError ? (
          <DimensionSkeleton legend="Account" />
        ) : accountsError ? (
          <DimensionError legend="Account" />
        ) : accountOptions.length > 0 ? (
          <LabeledCheckboxGroup
            legend="Account"
            options={accountOptions}
            selected={value.account_ids}
            onToggle={val => toggleKey('account_ids', val)}
          />
        ) : null}

        {isLoading && !setupsError ? (
          <DimensionSkeleton legend="Setup" />
        ) : setupsError ? (
          <DimensionError legend="Setup" />
        ) : setupOptions.length > 0 ? (
          <LabeledCheckboxGroup
            legend="Setup"
            options={setupOptions}
            selected={value.setup_names}
            onToggle={val => toggleKey('setup_names', val)}
          />
        ) : null}

        {isLoading && !brokersError ? (
          <DimensionSkeleton legend="Broker" />
        ) : brokersError ? (
          <DimensionError legend="Broker" />
        ) : brokerOptions.length > 0 ? (
          <LabeledCheckboxGroup
            legend="Broker"
            options={brokerOptions}
            selected={value.brokers}
            onToggle={val => toggleKey('brokers', val)}
          />
        ) : null}
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
