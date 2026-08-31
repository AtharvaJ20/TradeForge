import { cn } from '@/lib/utils'
import type { MistakeType } from '../types'

/** All 13 canonical mistake labels from the domain spec. */
const ALL_MISTAKES: MistakeType[] = [
  'FOMO_ENTRY',
  'FOMO_EXIT',
  'OVERSIZED_POSITION',
  'NO_STOP_DEFINED',
  'MOVED_STOP_WIDER',
  'CUT_WINNER_EARLY',
  'HELD_THROUGH_STOP',
  'REVENGE_TRADE',
  'AVERAGING_DOWN',
  'ENTRY_TOO_EARLY',
  'ENTRY_TOO_LATE',
  'IGNORED_SIGNAL',
  'DISTRACTED',
]

const MISTAKE_LABELS: Record<MistakeType, string> = {
  FOMO_ENTRY: 'FOMO entry',
  FOMO_EXIT: 'FOMO exit',
  OVERSIZED_POSITION: 'Oversized position',
  NO_STOP_DEFINED: 'No stop defined',
  MOVED_STOP_WIDER: 'Moved stop wider',
  CUT_WINNER_EARLY: 'Cut winner early',
  HELD_THROUGH_STOP: 'Held through stop',
  REVENGE_TRADE: 'Revenge trade',
  AVERAGING_DOWN: 'Averaging down',
  ENTRY_TOO_EARLY: 'Entry too early',
  ENTRY_TOO_LATE: 'Entry too late',
  IGNORED_SIGNAL: 'Ignored signal',
  DISTRACTED: 'Distracted',
}

interface MistakesCheckboxGroupProps {
  value: MistakeType[]
  onChange: (value: MistakeType[]) => void
  /** Limit shown items (remaining behind "Show more"). Omit for full list. */
  visibleCount?: number
  disabled?: boolean
}

/** C-07 MistakesCheckboxGroup — multi-select mistake chips. */
export function MistakesCheckboxGroup({
  value,
  onChange,
  visibleCount,
  disabled = false,
}: MistakesCheckboxGroupProps) {
  const visibleMistakes = visibleCount !== undefined ? ALL_MISTAKES.slice(0, visibleCount) : ALL_MISTAKES

  const toggle = (mistake: MistakeType) => {
    if (disabled) return
    if (value.includes(mistake)) {
      onChange(value.filter((m) => m !== mistake))
    } else {
      onChange([...value, mistake])
    }
  }

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium text-text-primary">Mistakes</legend>
      <div role="group" className="flex flex-wrap gap-2">
        {visibleMistakes.map((mistake) => {
          const isChecked = value.includes(mistake)
          return (
            <button
              key={mistake}
              type="button"
              role="checkbox"
              aria-checked={isChecked}
              disabled={disabled}
              onClick={() => toggle(mistake)}
              className={cn(
                'rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus',
                isChecked
                  ? 'border-danger/50 bg-surface-danger text-danger-emphasis'
                  : 'border-border bg-surface-neutral text-text-secondary hover:border-text-secondary',
                disabled && 'cursor-not-allowed opacity-50',
              )}
            >
              {MISTAKE_LABELS[mistake]}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
