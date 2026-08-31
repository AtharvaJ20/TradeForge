import { cn } from '@/lib/utils'
import type { EmotionType } from '../types'

const EMOTIONS: EmotionType[] = [
  'CALM',
  'CONFIDENT',
  'ANXIOUS',
  'FEARFUL',
  'GREEDY',
  'FRUSTRATED',
  'EUPHORIC',
  'BORED',
]

const EMOTION_LABELS: Record<EmotionType, string> = {
  CALM: 'Calm',
  CONFIDENT: 'Confident',
  ANXIOUS: 'Anxious',
  FEARFUL: 'Fearful',
  GREEDY: 'Greedy',
  FRUSTRATED: 'Frustrated',
  EUPHORIC: 'Euphoric',
  BORED: 'Bored',
}

const EMOTION_COLOR: Record<EmotionType, string> = {
  CALM: 'border-success/40 bg-success-subtle text-success-emphasis',
  CONFIDENT: 'border-success/40 bg-success-subtle text-success-emphasis',
  ANXIOUS: 'border-warning/40 bg-surface-warning text-warning-emphasis',
  FEARFUL: 'border-danger/40 bg-surface-danger text-danger-emphasis',
  GREEDY: 'border-warning/40 bg-surface-warning text-warning-emphasis',
  FRUSTRATED: 'border-danger/40 bg-surface-danger text-danger-emphasis',
  EUPHORIC: 'border-info/40 bg-surface-info text-info',
  BORED: 'border-border bg-surface-subtle text-text-secondary',
}

interface EmotionChipGroupProps {
  label: string
  value: EmotionType | null
  onChange: (value: EmotionType | null) => void
  disabled?: boolean
}

/** Single-select emotion chip group (shared by before/during/after fields). */
export function EmotionChipGroup({ label, value, onChange, disabled = false }: EmotionChipGroupProps) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium text-text-primary">{label}</legend>
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
        {EMOTIONS.map((emotion) => {
          const isSelected = value === emotion
          return (
            <button
              key={emotion}
              type="button"
              role="radio"
              aria-checked={isSelected}
              disabled={disabled}
              onClick={() => {
                if (disabled) return
                onChange(isSelected ? null : emotion)
              }}
              className={cn(
                'rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus',
                isSelected
                  ? EMOTION_COLOR[emotion]
                  : 'border-border bg-surface-neutral text-text-secondary hover:border-text-secondary',
                disabled && 'cursor-not-allowed opacity-50',
              )}
            >
              {EMOTION_LABELS[emotion]}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
