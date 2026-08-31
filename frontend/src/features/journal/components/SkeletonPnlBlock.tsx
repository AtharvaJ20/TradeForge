/** C-03 SkeletonPnlBlock — loading placeholder for PnlStatusBlock. */
export function SkeletonPnlBlock() {
  return (
    <div
      className="rounded-lg border border-border p-4 space-y-2"
      aria-hidden="true"
      role="presentation"
    >
      <div className="h-3 rounded bg-surface-subtle w-2/5 animate-shimmer [background-image:linear-gradient(90deg,var(--color-surface-subtle)_25%,var(--color-surface-neutral)_50%,var(--color-surface-subtle)_75%)] [background-size:200%_100%] motion-reduce:animate-none" />
      <div className="h-3 rounded bg-surface-subtle w-[70%] animate-shimmer [background-image:linear-gradient(90deg,var(--color-surface-subtle)_25%,var(--color-surface-neutral)_50%,var(--color-surface-subtle)_75%)] [background-size:200%_100%] motion-reduce:animate-none" />
    </div>
  )
}
