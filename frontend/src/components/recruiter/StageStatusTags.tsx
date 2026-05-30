import type { ReactNode } from 'react'
import { formatFieldLabel } from '@/lib/format'

const STAGE_TAG_BASE = 'inline-flex items-center rounded-full border font-semibold tracking-wide'
const STAGE_TAG_DEFAULT_SIZE = 'px-3 py-1 text-sm'
const STAGE_TAG_COMPACT_SIZE = 'px-2.5 py-0.5 text-xs'

const STATUS_STYLES: Record<string, string> = {
  active: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  inactive: 'border-slate-300 bg-slate-100 text-slate-700',
  hired: 'border-indigo-200 bg-indigo-50 text-indigo-900',
}

export function StageTag({ stage, compact = false }: { stage: string; compact?: boolean }) {
  const sizeClass = compact ? STAGE_TAG_COMPACT_SIZE : STAGE_TAG_DEFAULT_SIZE
  return (
    <span className={`${STAGE_TAG_BASE} ${sizeClass} border-violet-200 bg-violet-50 text-violet-900`}>
      {formatFieldLabel(stage.replace(/_/g, ' ')) || stage}
    </span>
  )
}

export function StatusTag({ kind, compact = false }: { kind: string; compact?: boolean }) {
  const sizeClass = compact ? STAGE_TAG_COMPACT_SIZE : STAGE_TAG_DEFAULT_SIZE
  const style = STATUS_STYLES[kind] ?? 'border-slate-300 bg-slate-50 text-slate-800'
  return (
    <span className={`${STAGE_TAG_BASE} ${sizeClass} ${style}`}>{formatFieldLabel(kind)}</span>
  )
}

export function StageStatusField({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <div>{children}</div>
    </div>
  )
}
