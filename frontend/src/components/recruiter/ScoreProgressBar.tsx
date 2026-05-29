type ScoreProgressBarProps = {
  value: number | null | undefined
  className?: string
}

export function ScoreProgressBar({ value, className = '' }: ScoreProgressBarProps) {
  const pct = value != null && !Number.isNaN(value) ? Math.min(100, Math.max(0, value * 100)) : 0
  const width = value != null && !Number.isNaN(value) ? `${pct}%` : '0%'
  return (
    <div
      className={`h-2 w-full min-w-[6rem] max-w-xs overflow-hidden rounded-full bg-slate-100 ${className}`}
      role="progressbar"
      aria-valuenow={value != null ? pct : undefined}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full rounded-full bg-indigo-500 transition-[width]"
        style={{ width }}
      />
    </div>
  )
}
