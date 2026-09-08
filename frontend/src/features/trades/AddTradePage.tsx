import { useState, useEffect, useId } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAccount } from '@/features/accounts/context/AccountContext'
import { ApiError } from '@/lib/api-client'
import { tradesApi } from './api'
import type { CreateTradeBody } from './types'

// ---------------------------------------------------------------------------
// Local types
// ---------------------------------------------------------------------------

interface FillRow {
  id: string
  side: 'BUY' | 'SELL'
  quantity: string
  price: string
  date: string
  time: string
}

interface FillErrors {
  quantity?: string
  price?: string
  date?: string
  time?: string
  order?: string
}

interface FormErrors {
  symbol?: string
  accountId?: string
  exchangeSegment?: string
  instrumentType?: string
  expiryDate?: string
  strikePrice?: string
  productType?: string
  fills?: FillErrors[]
}

type ExchangeSegment = 'NSE_EQ' | 'NSE_FO' | 'BSE_EQ'
type InstrumentType = 'EQ' | 'FUT' | 'CE' | 'PE'
type ProductType = 'MIS' | 'CNC' | 'NRML'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function generateId(): string {
  return Math.random().toString(36).slice(2)
}

function makeFillRow(): FillRow {
  return { id: generateId(), side: 'BUY', quantity: '', price: '', date: '', time: '' }
}

function fillTimestamp(date: string, time: string): string {
  return `${date}T${time}:00+05:30`
}

function needsExpiry(type: InstrumentType | ''): boolean {
  return type === 'FUT' || type === 'CE' || type === 'PE'
}

function needsStrike(type: InstrumentType | ''): boolean {
  return type === 'CE' || type === 'PE'
}

/** Returns the product_type option that is invalid for the given instrument type. */
function invalidProductType(instrumentType: InstrumentType | ''): ProductType | null {
  if (instrumentType === 'EQ') return 'NRML'
  if (instrumentType === 'FUT' || instrumentType === 'CE' || instrumentType === 'PE') return 'CNC'
  return null
}

function invalidProductTypeHelper(instrumentType: InstrumentType | ''): string | null {
  if (instrumentType === 'EQ')
    return 'NRML is not valid for equity instruments — use MIS (intraday) or CNC (delivery).'
  if (instrumentType === 'FUT' || instrumentType === 'CE' || instrumentType === 'PE')
    return 'CNC is not valid for F&O instruments — use MIS (intraday) or NRML (overnight).'
  return null
}

// ---------------------------------------------------------------------------
// Reusable field row layout
// ---------------------------------------------------------------------------

function FieldRow({ children }: { children: React.ReactNode }) {
  return <div className="mb-4">{children}</div>
}

function Label({ htmlFor, children }: { htmlFor: string; children: React.ReactNode }) {
  return (
    <label
      htmlFor={htmlFor}
      className="mb-1.5 block text-sm font-medium text-text-primary"
    >
      {children}
    </label>
  )
}

function InputClass() {
  return 'w-full rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary focus:border-border-focus focus:outline-none focus:ring-2 focus:ring-border-focus/20'
}

function FieldError({ message }: { message: string }) {
  return (
    <p role="alert" className="mt-1 text-xs text-danger-emphasis">
      {message}
    </p>
  )
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-4 text-base font-semibold text-text-primary">{children}</h2>
  )
}

// ---------------------------------------------------------------------------
// AddTradePage
// ---------------------------------------------------------------------------

export function AddTradePage() {
  const navigate = useNavigate()
  const uid = useId()
  const { accounts, selectedAccount, isLoading: accountsLoading } = useAccount()

  // Form state
  const [accountId, setAccountId] = useState<string>('')
  const [symbol, setSymbol] = useState('')
  const [exchangeSegment, setExchangeSegment] = useState<ExchangeSegment | ''>('NSE_EQ')
  const [instrumentType, setInstrumentType] = useState<InstrumentType | ''>('EQ')
  const [expiryDate, setExpiryDate] = useState('')
  const [strikePrice, setStrikePrice] = useState('')
  const [productType, setProductType] = useState<ProductType | ''>('MIS')
  const [fills, setFills] = useState<FillRow[]>([makeFillRow()])
  const [plannedStop, setPlannedStop] = useState('')
  const [plannedTarget, setPlannedTarget] = useState('')

  // UI state
  const [errors, setErrors] = useState<FormErrors>({})
  const [apiError, setApiError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Default account to selected on load
  useEffect(() => {
    if (!accountsLoading && selectedAccount && !accountId) {
      setAccountId(selectedAccount.id)
    }
  }, [accountsLoading, selectedAccount, accountId])

  // When instrument type changes, reset invalid product type and clear conditional fields
  function handleInstrumentTypeChange(newType: InstrumentType | '') {
    setInstrumentType(newType)
    const invalid = invalidProductType(newType)
    if (invalid && productType === invalid) {
      setProductType('')
    }
    if (!needsExpiry(newType)) setExpiryDate('')
    if (!needsStrike(newType)) setStrikePrice('')
  }

  // Active accounts only (for the selector)
  const activeAccounts = accounts.filter((a) => a.status === 'ACTIVE')

  // Derived display flags
  const showExpiry = needsExpiry(instrumentType)
  const showStrike = needsStrike(instrumentType)
  const disabledProductType = invalidProductType(instrumentType)
  const productTypeHelper = invalidProductTypeHelper(instrumentType)

  // Fill operations
  function addFill() {
    if (fills.length < 20) {
      setFills((prev) => [...prev, makeFillRow()])
    }
  }

  function removeFill(index: number) {
    setFills((prev) => prev.filter((_, i) => i !== index))
  }

  function updateFill(index: number, patch: Partial<FillRow>) {
    setFills((prev) => prev.map((f, i) => (i === index ? { ...f, ...patch } : f)))
  }

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------

  function validate(): FormErrors {
    const errs: FormErrors = {}

    if (!symbol.trim()) errs.symbol = 'Symbol is required.'
    if (!exchangeSegment) errs.exchangeSegment = 'Exchange segment is required.'
    if (!instrumentType) errs.instrumentType = 'Instrument type is required.'
    if (showExpiry && !expiryDate) errs.expiryDate = 'Expiry date is required for this instrument type.'
    if (showStrike && !strikePrice) errs.strikePrice = 'Strike price is required for this instrument type.'
    if (!productType) errs.productType = 'Product type is required.'

    const fillErrors: FillErrors[] = fills.map((fill) => {
      const fe: FillErrors = {}
      const qty = parseFloat(fill.quantity)
      if (!fill.quantity || isNaN(qty) || qty <= 0) fe.quantity = 'Quantity must be greater than 0.'
      const pr = parseFloat(fill.price)
      if (!fill.price || isNaN(pr) || pr <= 0) fe.price = 'Price must be greater than 0.'
      if (!fill.date) fe.date = 'Date is required.'
      if (!fill.time) fe.time = 'Time is required.'
      return fe
    })

    // Chronological order check (only when individual fields are otherwise valid)
    for (let i = 1; i < fills.length; i++) {
      const prev = fills[i - 1]
      const curr = fills[i]
      if (prev.date && prev.time && curr.date && curr.time) {
        const prevTs = `${prev.date}T${prev.time}:00+05:30`
        const currTs = `${curr.date}T${curr.time}:00+05:30`
        if (currTs <= prevTs) {
          fillErrors[i] = {
            ...fillErrors[i],
            order: 'Fill must be in chronological order — timestamp must be after the previous fill.',
          }
        }
      }
    }

    const hasAnyFillError = fillErrors.some((fe) => Object.keys(fe).length > 0)
    if (hasAnyFillError) errs.fills = fillErrors

    return errs
  }

  // ---------------------------------------------------------------------------
  // Submit
  // ---------------------------------------------------------------------------

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setApiError(null)

    const errs = validate()
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }
    setErrors({})

    const body: CreateTradeBody = {
      account_id: accountId,
      instrument: {
        symbol: symbol.trim(),
        exchange_segment: exchangeSegment as ExchangeSegment,
        instrument_type: instrumentType as InstrumentType,
        ...(showExpiry && expiryDate ? { expiry_date: expiryDate } : {}),
        ...(showStrike && strikePrice ? { strike_price: strikePrice } : {}),
      },
      product_type: productType as 'MIS' | 'CNC' | 'NRML',
      fills: fills.map((fill) => ({
        side: fill.side,
        quantity: fill.quantity,
        price: fill.price,
        fill_timestamp: fillTimestamp(fill.date, fill.time),
      })),
      ...(plannedStop ? { planned_stop: plannedStop } : {}),
      ...(plannedTarget ? { planned_target: plannedTarget } : {}),
    }

    setIsSubmitting(true)
    try {
      await tradesApi.create(body)
      navigate('/trades', { state: { successMessage: 'Trade added successfully.' } })
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.detail)
      } else {
        setApiError('An unexpected error occurred. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-text-primary">Add Trade</h1>

      {apiError && (
        <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
          {apiError}
        </div>
      )}

      <form onSubmit={(e) => void handleSubmit(e)} noValidate>
        {/* ------------------------------------------------------------------ */}
        {/* Section 1 — Instrument                                              */}
        {/* ------------------------------------------------------------------ */}
        <section className="mb-8 rounded-xl border border-border bg-surface-base p-6">
          <SectionHeading>Instrument</SectionHeading>

          {/* Account */}
          <FieldRow>
            <Label htmlFor={`${uid}-account`}>Account</Label>
            <select
              id={`${uid}-account`}
              aria-label="Account"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className={InputClass()}
            >
              <option value="">Select account…</option>
              {activeAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name}
                </option>
              ))}
            </select>
            {errors.accountId && <FieldError message={errors.accountId} />}
          </FieldRow>

          {/* Symbol */}
          <FieldRow>
            <Label htmlFor={`${uid}-symbol`}>Symbol</Label>
            <input
              id={`${uid}-symbol`}
              aria-label="Symbol"
              type="text"
              placeholder="RELIANCE, NIFTY24OCTFUT"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className={InputClass()}
            />
            {errors.symbol && <FieldError message={errors.symbol} />}
          </FieldRow>

          {/* Exchange Segment */}
          <FieldRow>
            <Label htmlFor={`${uid}-exchange_segment`}>Exchange Segment</Label>
            <select
              id={`${uid}-exchange_segment`}
              aria-label="Exchange Segment"
              value={exchangeSegment}
              onChange={(e) => setExchangeSegment(e.target.value as ExchangeSegment | '')}
              className={InputClass()}
            >
              <option value="">Select segment…</option>
              <option value="NSE_EQ">NSE_EQ</option>
              <option value="NSE_FO">NSE_FO</option>
              <option value="BSE_EQ">BSE_EQ</option>
            </select>
            {errors.exchangeSegment && <FieldError message={errors.exchangeSegment} />}
          </FieldRow>

          {/* Instrument Type */}
          <FieldRow>
            <Label htmlFor={`${uid}-instrument_type`}>Instrument Type</Label>
            <select
              id={`${uid}-instrument_type`}
              aria-label="Instrument Type"
              value={instrumentType}
              onChange={(e) => handleInstrumentTypeChange(e.target.value as InstrumentType | '')}
              className={InputClass()}
            >
              <option value="">Select type…</option>
              <option value="EQ">EQ</option>
              <option value="FUT">FUT</option>
              <option value="CE">CE</option>
              <option value="PE">PE</option>
            </select>
            {errors.instrumentType && <FieldError message={errors.instrumentType} />}
          </FieldRow>

          {/* Expiry Date (conditional) */}
          {showExpiry && (
            <FieldRow>
              <Label htmlFor={`${uid}-expiry_date`}>Expiry Date</Label>
              <input
                id={`${uid}-expiry_date`}
                aria-label="Expiry Date"
                type="date"
                value={expiryDate}
                onChange={(e) => setExpiryDate(e.target.value)}
                className={InputClass()}
              />
              {errors.expiryDate && <FieldError message={errors.expiryDate} />}
            </FieldRow>
          )}

          {/* Strike Price (conditional) */}
          {showStrike && (
            <FieldRow>
              <Label htmlFor={`${uid}-strike_price`}>Strike Price</Label>
              <input
                id={`${uid}-strike_price`}
                aria-label="Strike Price"
                type="number"
                min="0.01"
                step="0.05"
                placeholder="e.g. 18000"
                value={strikePrice}
                onChange={(e) => setStrikePrice(e.target.value)}
                className={InputClass()}
              />
              {errors.strikePrice && <FieldError message={errors.strikePrice} />}
            </FieldRow>
          )}

          {/* Product Type */}
          <FieldRow>
            <Label htmlFor={`${uid}-product_type`}>Product Type</Label>
            <select
              id={`${uid}-product_type`}
              aria-label="Product Type"
              value={productType}
              onChange={(e) => setProductType(e.target.value as ProductType | '')}
              className={InputClass()}
            >
              <option value="">Select product type…</option>
              <option value="MIS">MIS (Intraday)</option>
              <option value="CNC" disabled={disabledProductType === 'CNC'}>
                CNC (Delivery)
              </option>
              <option value="NRML" disabled={disabledProductType === 'NRML'}>
                NRML (F&amp;O Overnight)
              </option>
            </select>
            {productTypeHelper && (
              <p className="mt-1 text-xs text-text-secondary">{productTypeHelper}</p>
            )}
            {errors.productType && <FieldError message={errors.productType} />}
          </FieldRow>
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* Section 2 — Fills                                                   */}
        {/* ------------------------------------------------------------------ */}
        <section className="mb-8 rounded-xl border border-border bg-surface-base p-6">
          <SectionHeading>Fills</SectionHeading>

          <div className="flex flex-col gap-4">
            {fills.map((fill, index) => {
              const fe = errors.fills?.[index] ?? {}
              return (
                <div
                  key={fill.id}
                  data-testid="fill-row"
                  className="rounded-lg border border-border bg-surface-subtle p-4"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
                      Fill {index + 1}
                    </span>
                    {index > 0 && (
                      <button
                        type="button"
                        onClick={() => removeFill(index)}
                        className="text-xs text-danger-emphasis hover:underline focus:outline-none"
                      >
                        Remove
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                    {/* Side */}
                    <div>
                      <label
                        htmlFor={`fill-${index}-side`}
                        className="mb-1 block text-xs font-medium text-text-primary"
                      >
                        Side
                      </label>
                      <select
                        id={`fill-${index}-side`}
                        value={fill.side}
                        onChange={(e) => updateFill(index, { side: e.target.value as 'BUY' | 'SELL' })}
                        className="w-full rounded border border-border bg-surface-base px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-border-focus"
                      >
                        <option value="BUY">BUY</option>
                        <option value="SELL">SELL</option>
                      </select>
                    </div>

                    {/* Quantity */}
                    <div>
                      <label
                        htmlFor={`fill-${index}-quantity`}
                        className="mb-1 block text-xs font-medium text-text-primary"
                      >
                        Quantity
                      </label>
                      <input
                        id={`fill-${index}-quantity`}
                        type="number"
                        min="0.01"
                        step="1"
                        placeholder="10"
                        value={fill.quantity}
                        onChange={(e) => updateFill(index, { quantity: e.target.value })}
                        className="w-full rounded border border-border bg-surface-base px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-border-focus"
                      />
                      {fe.quantity && <FieldError message={fe.quantity} />}
                    </div>

                    {/* Price */}
                    <div>
                      <label
                        htmlFor={`fill-${index}-price`}
                        className="mb-1 block text-xs font-medium text-text-primary"
                      >
                        Price
                      </label>
                      <input
                        id={`fill-${index}-price`}
                        type="number"
                        min="0.01"
                        step="0.05"
                        placeholder="500"
                        value={fill.price}
                        onChange={(e) => updateFill(index, { price: e.target.value })}
                        className="w-full rounded border border-border bg-surface-base px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-border-focus"
                      />
                      {fe.price && <FieldError message={fe.price} />}
                    </div>

                    {/* Date */}
                    <div>
                      <label
                        htmlFor={`fill-${index}-date`}
                        className="mb-1 block text-xs font-medium text-text-primary"
                      >
                        Date
                      </label>
                      <input
                        id={`fill-${index}-date`}
                        type="date"
                        value={fill.date}
                        onChange={(e) => updateFill(index, { date: e.target.value })}
                        className="w-full rounded border border-border bg-surface-base px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-border-focus"
                      />
                      {fe.date && <FieldError message={fe.date} />}
                    </div>

                    {/* Time */}
                    <div>
                      <label
                        htmlFor={`fill-${index}-time`}
                        className="mb-1 block text-xs font-medium text-text-primary"
                      >
                        Time
                      </label>
                      <input
                        id={`fill-${index}-time`}
                        type="time"
                        value={fill.time}
                        onChange={(e) => updateFill(index, { time: e.target.value })}
                        className="w-full rounded border border-border bg-surface-base px-2 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-border-focus"
                      />
                      {fe.time && <FieldError message={fe.time} />}
                    </div>
                  </div>

                  {fe.order && (
                    <p role="alert" className="mt-2 text-xs text-danger-emphasis">
                      {fe.order}
                    </p>
                  )}
                </div>
              )
            })}
          </div>

          {fills.length < 20 && (
            <button
              type="button"
              onClick={addFill}
              className="mt-4 rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-subtle hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              Add fill
            </button>
          )}
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* Section 3 — Plan (optional)                                         */}
        {/* ------------------------------------------------------------------ */}
        <section className="mb-8 rounded-xl border border-border bg-surface-base p-6">
          <SectionHeading>Plan (optional)</SectionHeading>

          <div className="grid grid-cols-2 gap-4">
            <FieldRow>
              <Label htmlFor={`${uid}-planned_stop`}>Planned Stop</Label>
              <input
                id={`${uid}-planned_stop`}
                type="number"
                min="0.01"
                step="0.05"
                placeholder="490.00"
                value={plannedStop}
                onChange={(e) => setPlannedStop(e.target.value)}
                className={InputClass()}
              />
            </FieldRow>

            <FieldRow>
              <Label htmlFor={`${uid}-planned_target`}>Planned Target</Label>
              <input
                id={`${uid}-planned_target`}
                type="number"
                min="0.01"
                step="0.05"
                placeholder="520.00"
                value={plannedTarget}
                onChange={(e) => setPlannedTarget(e.target.value)}
                className={InputClass()}
              />
            </FieldRow>
          </div>
        </section>

        {/* Submit */}
        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-emphasis focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? 'Submitting…' : 'Add Trade'}
        </button>
      </form>
    </div>
  )
}
