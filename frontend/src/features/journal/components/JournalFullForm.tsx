import { useEffect } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { calcPlannedRisk, calcRR } from '@/lib/utils'
import { DisciplineScoreInput } from './DisciplineScoreInput'
import { MistakesCheckboxGroup } from './MistakesCheckboxGroup'
import { EmotionChipGroup } from './EmotionChipGroup'
import type { JournalEntryWrite, EmotionType, MistakeType, JournalEntry, TradeForJournal } from '../types'

const FullSchema = z.object({
  planned_entry: z.string().nullable(),
  planned_stop: z.string().nullable(),
  planned_target: z.string().nullable(),
  setup_name: z.string().nullable(),
  notes: z.string().nullable(),
  discipline_score: z.number().int().min(1).max(10).nullable(),
  mistakes: z.array(z.string()),
  emotion_before: z.string().nullable(),
  emotion_during: z.string().nullable(),
  emotion_after: z.string().nullable(),
  change_reason: z.string().nullable(),
})
type FullForm = z.infer<typeof FullSchema>

interface JournalFullFormProps {
  entry: JournalEntry | null
  trade: TradeForJournal
  isExisting: boolean
  isSaving: boolean
  onSave: (data: JournalEntryWrite) => void
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="text-sm font-medium text-text-primary">
        {label}
      </label>
      {children}
    </div>
  )
}

const inputClass =
  'w-full rounded-md border border-border bg-surface-neutral px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50'

/** C-05 JournalFullForm — full annotated journal entry form. */
export function JournalFullForm({ entry, trade, isExisting, isSaving, onSave }: JournalFullFormProps) {
  const { register, control, handleSubmit, watch, setValue, formState: { errors } } = useForm<FullForm>({
    resolver: zodResolver(FullSchema),
    defaultValues: {
      planned_entry: entry?.planned_entry ?? null,
      planned_stop: entry?.planned_stop ?? null,
      planned_target: entry?.planned_target ?? null,
      setup_name: entry?.setup_name ?? null,
      notes: entry?.notes ?? null,
      discipline_score: entry?.discipline_score ?? null,
      mistakes: entry?.mistakes ?? [],
      emotion_before: entry?.emotion_before ?? null,
      emotion_during: entry?.emotion_during ?? null,
      emotion_after: entry?.emotion_after ?? null,
      change_reason: null,
    },
  })

  const plannedStop = watch('planned_stop')
  const plannedTarget = watch('planned_target')
  const plannedEntry = watch('planned_entry')
  const avgEntry = trade.averageEntry ?? plannedEntry

  // Derive computed display values (not stored — calculated on render)
  const plannedRisk = calcPlannedRisk(avgEntry, plannedStop, trade.totalEntryQuantity)
  const rr = calcRR(avgEntry, plannedStop, plannedTarget)

  // Propagate entry field default from trade avg entry when blank
  useEffect(() => {
    if (!entry?.planned_entry && trade.averageEntry) {
      setValue('planned_entry', trade.averageEntry)
    }
  }, [entry, trade.averageEntry, setValue])

  const onSubmit = (data: FullForm) => {
    onSave({
      planned_entry: data.planned_entry || null,
      planned_stop: data.planned_stop || null,
      planned_target: data.planned_target || null,
      setup_name: data.setup_name || null,
      notes: data.notes || null,
      discipline_score: data.discipline_score,
      mistakes: data.mistakes.length > 0 ? data.mistakes : null,
      emotion_before: data.emotion_before,
      emotion_during: data.emotion_during,
      emotion_after: data.emotion_after,
      change_reason: isExisting ? (data.change_reason || null) : null,
    })
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6" noValidate>
      {/* Risk fields */}
      <section aria-label="Risk plan" className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Field label="Planned Entry" htmlFor="planned_entry">
          <input id="planned_entry" type="number" step="0.01" {...register('planned_entry')} disabled={isSaving} className={inputClass} placeholder="e.g. 2450.50" />
        </Field>
        <Field label="Planned Stop" htmlFor="planned_stop">
          <input
            id="planned_stop"
            type="number"
            step="0.01"
            {...register('planned_stop')}
            disabled={isSaving}
            className={inputClass}
            placeholder="e.g. 2420.00"
          />
        </Field>
        <Field label="Planned Target" htmlFor="planned_target">
          <input id="planned_target" type="number" step="0.01" {...register('planned_target')} disabled={isSaving} className={inputClass} placeholder="e.g. 2520.00" />
        </Field>
        <div className="space-y-1">
          <p className="text-xs text-text-secondary">Planned Risk</p>
          <p className="text-sm font-medium text-text-primary">{plannedRisk ?? '—'}</p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-text-secondary">Planned R:R</p>
          <p className="text-sm font-medium text-text-primary">{rr ?? '—'}</p>
        </div>
      </section>

      {/* Setup */}
      <Field label="Setup Name" htmlFor="setup_name">
        <input id="setup_name" type="text" {...register('setup_name')} disabled={isSaving} className={inputClass} placeholder="e.g. Opening range breakout" />
      </Field>

      {/* Emotions */}
      <section className="space-y-4" aria-label="Emotional state">
        <Controller
          name="emotion_before"
          control={control}
          render={({ field }) => (
            <EmotionChipGroup
              label="Emotion before trade"
              value={field.value as EmotionType | null}
              onChange={field.onChange}
              disabled={isSaving}
            />
          )}
        />
        <Controller
          name="emotion_during"
          control={control}
          render={({ field }) => (
            <EmotionChipGroup
              label="Emotion during trade"
              value={field.value as EmotionType | null}
              onChange={field.onChange}
              disabled={isSaving}
            />
          )}
        />
        <Controller
          name="emotion_after"
          control={control}
          render={({ field }) => (
            <EmotionChipGroup
              label="Emotion after trade"
              value={field.value as EmotionType | null}
              onChange={field.onChange}
              disabled={isSaving}
            />
          )}
        />
      </section>

      {/* Discipline & Mistakes */}
      <Controller
        name="discipline_score"
        control={control}
        render={({ field }) => (
          <DisciplineScoreInput value={field.value} onChange={field.onChange} disabled={isSaving} />
        )}
      />
      <Controller
        name="mistakes"
        control={control}
        render={({ field }) => (
          <MistakesCheckboxGroup
            value={field.value as MistakeType[]}
            onChange={field.onChange}
            disabled={isSaving}
          />
        )}
      />

      {/* Notes */}
      <Field label="Notes" htmlFor="notes">
        <textarea
          id="notes"
          rows={4}
          {...register('notes')}
          disabled={isSaving}
          className={inputClass}
          placeholder="What happened? What did you learn?"
        />
      </Field>

      {/* Change reason (edits only) */}
      {isExisting && (
        <Field label="Reason for edit" htmlFor="change_reason">
          <input
            id="change_reason"
            type="text"
            {...register('change_reason')}
            disabled={isSaving}
            className={inputClass}
            placeholder="Why are you updating this entry?"
          />
          {errors.change_reason && (
            <p role="alert" className="text-xs text-danger-emphasis">{errors.change_reason.message}</p>
          )}
        </Field>
      )}

      <button
        type="submit"
        disabled={isSaving}
        className="w-full rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSaving ? 'Saving…' : isExisting ? 'Update entry' : 'Save entry'}
      </button>
    </form>
  )
}
