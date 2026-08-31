import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { DisciplineScoreInput } from './DisciplineScoreInput'
import { MistakesCheckboxGroup } from './MistakesCheckboxGroup'
import { EmotionChipGroup } from './EmotionChipGroup'
import type { JournalEntryWrite, EmotionType, MistakeType } from '../types'

const QuickSchema = z.object({
  discipline_score: z.number().int().min(1).max(10).nullable(),
  emotion_after: z.string().nullable(),
  mistakes: z.array(z.string()),
})
type QuickForm = z.infer<typeof QuickSchema>

interface JournalQuickCaptureProps {
  defaultValues?: Partial<QuickForm>
  isSaving: boolean
  onSave: (data: JournalEntryWrite) => void
  onExpandForm: () => void
}

/** C-04 JournalQuickCapture — minimal 3-field post-trade form (score + emotion + mistakes). */
export function JournalQuickCapture({
  defaultValues,
  isSaving,
  onSave,
  onExpandForm,
}: JournalQuickCaptureProps) {
  const { control, handleSubmit } = useForm<QuickForm>({
    resolver: zodResolver(QuickSchema),
    defaultValues: {
      discipline_score: defaultValues?.discipline_score ?? null,
      emotion_after: defaultValues?.emotion_after ?? null,
      mistakes: defaultValues?.mistakes ?? [],
    },
  })

  const onSubmit = (data: QuickForm) => {
    onSave({
      discipline_score: data.discipline_score,
      emotion_after: data.emotion_after,
      mistakes: data.mistakes.length > 0 ? data.mistakes : null,
    })
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
      <Controller
        name="discipline_score"
        control={control}
        render={({ field }) => (
          <DisciplineScoreInput
            value={field.value}
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
            label="How did you feel after?"
            value={field.value as EmotionType | null}
            onChange={field.onChange}
            disabled={isSaving}
          />
        )}
      />

      <Controller
        name="mistakes"
        control={control}
        render={({ field }) => (
          <MistakesCheckboxGroup
            value={field.value as MistakeType[]}
            onChange={field.onChange}
            visibleCount={6}
            disabled={isSaving}
          />
        )}
      />

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={isSaving}
          className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSaving ? 'Saving…' : 'Save entry'}
        </button>
        <button
          type="button"
          onClick={onExpandForm}
          disabled={isSaving}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:border-text-secondary hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          More fields →
        </button>
      </div>
    </form>
  )
}
