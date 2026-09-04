import { useRDistribution } from '../hooks/useRDistribution'
import type { AnalyticsFilterParams, RBucket, RDistribution } from '../types'
import { formatSigned, formatDecimal } from '../formatters'

// ---------------------------------------------------------------------------
// Bar chart
// ---------------------------------------------------------------------------

interface BucketBarProps {
  bucket: RBucket
  maxCount: number
  totalWithR: number
}

function BucketBar({ bucket, maxCount, totalWithR }: BucketBarProps) {
  const pct = totalWithR > 0 ? (bucket.count / totalWithR) * 100 : 0
  const barWidth = maxCount > 0 ? (bucket.count / maxCount) * 100 : 0
  const isLoss = bucket.upper !== null && parseFloat(bucket.upper) <= 0
  const isWin = bucket.lower !== null && parseFloat(bucket.lower) >= 0

  const barColor = isWin
    ? 'bg-success-emphasis'
    : isLoss
      ? 'bg-danger-emphasis'
      : 'bg-text-secondary'

  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 text-right text-xs tabular-nums text-text-secondary">
        {bucket.label}
      </span>
      <div className="flex flex-1 items-center gap-2">
        <div className="h-5 flex-1 overflow-hidden rounded-sm bg-surface-subtle">
          <div
            className={`h-full rounded-sm ${barColor} transition-all duration-300`}
            style={{ width: `${barWidth}%` }}
            aria-label={`${bucket.label}: ${bucket.count} trades`}
          />
        </div>
        <span className="w-8 shrink-0 text-right text-xs tabular-nums text-text-primary">
          {bucket.count}
        </span>
        <span className="w-12 shrink-0 text-right text-xs tabular-nums text-text-secondary">
          {pct.toFixed(1)}%
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Display (accepts already-fetched data)
// ---------------------------------------------------------------------------

function RDistributionDisplay({ data }: { data: RDistribution }) {
  const maxCount = Math.max(...data.buckets.map(b => b.count), 1)

  return (
    <div className="space-y-4">
      {/* Summary stats */}
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs">
        <span className="text-text-secondary">
          With R:{' '}
          <span className="font-semibold tabular-nums text-text-primary">
            {data.coverage_count}/{data.total_count}
          </span>
        </span>
        {data.mean_r !== null && (
          <span className="text-text-secondary">
            Mean:{' '}
            <span className="font-semibold tabular-nums text-text-primary">
              {formatSigned(data.mean_r)}R
            </span>
          </span>
        )}
        {data.median_r !== null && (
          <span className="text-text-secondary">
            Median:{' '}
            <span className="font-semibold tabular-nums text-text-primary">
              {formatSigned(data.median_r)}R
            </span>
          </span>
        )}
        {data.stddev_r !== null && (
          <span className="text-text-secondary">
            StdDev:{' '}
            <span className="font-semibold tabular-nums text-text-primary">
              {formatDecimal(data.stddev_r)}
            </span>
          </span>
        )}
      </div>

      {/* Column headers */}
      <div className="flex items-center gap-3">
        <span className="w-28 shrink-0 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Bucket
        </span>
        <div className="flex flex-1 items-center gap-2">
          <span className="flex-1 text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Distribution
          </span>
          <span className="w-8 shrink-0 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary">
            #
          </span>
          <span className="w-12 shrink-0 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary">
            %
          </span>
        </div>
      </div>

      {/* Bars */}
      <div className="space-y-2">
        {data.buckets.map(bucket => (
          <BucketBar
            key={bucket.label}
            bucket={bucket}
            maxCount={maxCount}
            totalWithR={data.coverage_count}
          />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Public card (owns fetching)
// ---------------------------------------------------------------------------

export function RDistributionCard({ params = {} }: { params?: AnalyticsFilterParams }) {
  const { data, isLoading, isError } = useRDistribution(params)

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="R-multiple distribution"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        R-Multiple Distribution
      </h2>

      {isLoading && (
        <div
          className="h-40 animate-pulse rounded-lg bg-surface-subtle"
          role="status"
          aria-label="Loading R-multiple distribution"
        />
      )}

      {isError && !isLoading && (
        <p className="text-sm text-danger-emphasis">Failed to load R-multiple distribution.</p>
      )}

      {data && !isLoading && data.insufficient_sample && (
        <p className="text-sm text-text-secondary" role="note">
          Need at least 5 trades with a planned stop to show R distribution.
        </p>
      )}

      {data && !isLoading && !data.insufficient_sample && (
        <RDistributionDisplay data={data} />
      )}
    </section>
  )
}
