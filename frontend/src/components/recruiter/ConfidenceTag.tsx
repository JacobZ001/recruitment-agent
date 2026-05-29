import { formatScorePercent } from '@/lib/format'

export function ConfidenceTag({ confidence }: { confidence: number | null | undefined }) {
  if (confidence == null || Number.isNaN(confidence)) return null
  let tone = 'border-slate-200 bg-slate-50 text-slate-700'
  if (confidence >= 0.75) tone = 'border-emerald-200 bg-emerald-50 text-emerald-900'
  else if (confidence >= 0.5) tone = 'border-amber-200 bg-amber-50 text-amber-900'
  else tone = 'border-orange-200 bg-orange-50 text-orange-900'
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${tone}`}
      title="Confidence"
    >
      Confidence {formatScorePercent(confidence)}
    </span>
  )
}
