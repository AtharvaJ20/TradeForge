import { useCallback, useRef } from 'react'
import { cn } from '@/lib/utils'

interface DisciplineScoreInputProps {
  value: number | null
  onChange: (value: number | null) => void
  /** When true the component is disabled (e.g. during a save). */
  disabled?: boolean
}

const SCORES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const

function scoreColor(score: number): string {
  if (score <= 3) return 'border-danger-emphasis text-danger-emphasis'
  if (score <= 6) return 'border-warning-emphasis text-warning-emphasis'
  return 'border-success-emphasis text-success-emphasis'
}

/** C-06 DisciplineScoreInput — 10 numbered circles, keyboard navigable. */
export function DisciplineScoreInput({ value, onChange, disabled = false }: DisciplineScoreInputProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  const handleClick = useCallback(
    (score: number) => {
      if (disabled) return
      // Click the selected score again → deselect
      onChange(value === score ? null : score)
    },
    [value, onChange, disabled],
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (disabled) return
      const current = value ?? 0
      if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
        e.preventDefault()
        const next = Math.min(10, current + 1)
        onChange(next === 0 ? 1 : next)
        // Move DOM focus to the newly selected button
        const btn = containerRef.current?.querySelector<HTMLButtonElement>(
          `[data-score="${next === 0 ? 1 : next}"]`,
        )
        btn?.focus()
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
        e.preventDefault()
        const prev = Math.max(1, current - 1)
        onChange(prev)
        const btn = containerRef.current?.querySelector<HTMLButtonElement>(`[data-score="${prev}"]`)
        btn?.focus()
      }
    },
    [value, onChange, disabled],
  )

  return (
    <fieldset className="space-y-1">
      <legend className="text-sm font-medium text-text-primary">Discipline Score</legend>
      <div
        ref={containerRef}
        role="radiogroup"
        aria-label="Discipline score out of 10"
        onKeyDown={handleKeyDown}
        className="flex flex-wrap gap-2"
      >
        {SCORES.map((score) => {
          const isSelected = value === score
          return (
            <button
              key={score}
              type="button"
              role="radio"
              aria-checked={isSelected}
              data-score={score}
              disabled={disabled}
              onClick={() => handleClick(score)}
              tabIndex={isSelected || (value === null && score === 1) ? 0 : -1}
              className={cn(
                'h-9 w-9 rounded-full border-2 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus',
                isSelected
                  ? cn('bg-current/10', scoreColor(score))
                  : 'border-border text-text-secondary hover:border-text-secondary',
                disabled && 'cursor-not-allowed opacity-50',
              )}
              aria-label={`Score ${score}`}
            >
              {score}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
