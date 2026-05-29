import type { CandidateViewResponse, ScoreCriterion } from '@/api/types'
import { ConfidenceTag } from '@/components/recruiter/ConfidenceTag'
import { ScoreProgressBar } from '@/components/recruiter/ScoreProgressBar'
import { formatFieldLabel, formatScalar, formatScorePercent } from '@/lib/format'

type CriterionScore = {
  score: number
  confidence: number
  reason?: string
}

type ScoreLayerEvaluation = {
  summary?: string
  criteria?: Record<string, CriterionScore>
}

type ScoreEvaluation = {
  normalized_score?: number
  confidence?: number
  explanation?: string
  source?: string
  context_version?: number
  stale?: boolean
  evidence_refs?: string[]
  l1_universal?: ScoreLayerEvaluation
  l2_role_specific?: ScoreLayerEvaluation
  l3_recruiter_preference?: ScoreLayerEvaluation
}

type EvaluationAggregate = {
  hard_filter?: Record<string, unknown> | null
  light?: ScoreEvaluation | null
  deep?: ScoreEvaluation | null
}

const LAYER_SECTIONS: {
  key: keyof ScoreEvaluation
  title: string
  source: string
}[] = [
  { key: 'l1_universal', title: 'Universal Competencies', source: 'universal' },
  { key: 'l2_role_specific', title: 'Role Specifics', source: 'role_specific' },
  { key: 'l3_recruiter_preference', title: 'Recruiter Preferences', source: 'recruiter_preference' },
]

function CriterionRow({
  name,
  item,
  source,
}: {
  name: string
  item: CriterionScore
  source: string
}) {
  return (
    <li className="space-y-2 rounded-md border border-slate-100 bg-slate-50/50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-slate-900">{formatFieldLabel(name)}</span>
        <span className="text-xs text-slate-500">{formatFieldLabel(source)}</span>
        <ConfidenceTag confidence={item.confidence} />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-semibold text-slate-800">
          Score {formatScorePercent(item.score)}
        </span>
        <ScoreProgressBar value={item.score} />
      </div>
      {item.reason?.trim() ? (
        <p className="text-xs leading-relaxed text-slate-600">{item.reason}</p>
      ) : null}
    </li>
  )
}

function LayerBlock({
  title,
  layer,
  criteriaFromScores,
}: {
  title: string
  layer: ScoreLayerEvaluation | undefined
  criteriaFromScores: ScoreCriterion[]
}) {
  const fromEval = layer?.criteria ?? {}
  const names = new Set([
    ...Object.keys(fromEval),
    ...criteriaFromScores.map((c) => c.name),
  ])
  if (names.size === 0 && !layer?.summary?.trim()) return null
  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      {layer?.summary?.trim() ? (
        <p className="text-sm text-slate-600">{layer.summary}</p>
      ) : null}
      <ul className="space-y-2">
        {[...names].sort().map((name) => {
          const item =
            fromEval[name] ??
            (() => {
              const c = criteriaFromScores.find((x) => x.name === name)
              if (!c || c.score == null) return null
              return {
                score: c.score,
                confidence: c.confidence ?? 0,
                reason: c.reason ?? undefined,
              }
            })()
          if (!item) return null
          const source =
            criteriaFromScores.find((x) => x.name === name)?.source ?? title.toLowerCase()
          return (
            <CriterionRow key={name} name={name} item={item} source={source} />
          )
        })}
      </ul>
    </div>
  )
}

function EvaluationMetaBlock({ label, block }: { label: string; block: ScoreEvaluation }) {
  const fields: { key: string; value: unknown }[] = [
    { key: 'normalized_score', value: block.normalized_score },
    { key: 'confidence', value: block.confidence },
    { key: 'source', value: block.source },
    { key: 'context_version', value: block.context_version },
    { key: 'stale', value: block.stale },
    { key: 'explanation', value: block.explanation },
  ]
  return (
    <details className="rounded-md border border-slate-200 bg-white p-3">
      <summary className="cursor-pointer text-sm font-semibold text-slate-800">{label}</summary>
      <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {fields.map(({ key, value }) => (
          <div key={key}>
            <dt className="text-xs text-slate-500">{formatFieldLabel(key)}</dt>
            <dd className="text-sm text-slate-900">
              {key.includes('score') && typeof value === 'number'
                ? formatScorePercent(value)
                : formatScalar(value)}
            </dd>
          </div>
        ))}
      </dl>
    </details>
  )
}

export function ScoresPane({
  scores,
  evaluation,
}: {
  scores: CandidateViewResponse['scores']
  evaluation?: Record<string, unknown> | null
}) {
  const evalAgg = (evaluation ?? {}) as EvaluationAggregate
  const active: ScoreEvaluation | null = evalAgg.deep ?? evalAgg.light ?? null
  const criteria = (scores.criteria ?? []) as ScoreCriterion[]
  const overall = scores.overall_score

  const criteriaBySource = (source: string) =>
    criteria.filter((c) => c.source === source || c.source.replace(/_/g, ' ') === source)

  return (
    <section className="space-y-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">Scores</h2>

      <div className="flex flex-wrap items-baseline gap-3 border-b border-slate-100 pb-4">
        <span className="text-sm font-semibold text-slate-700">Overall Score</span>
        <span className="text-2xl font-bold text-indigo-900">
          {formatScorePercent(overall?.value ?? null)}
        </span>
        {overall?.type ? (
          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-900">
            {overall.type}
          </span>
        ) : null}
        {overall?.value != null ? <ScoreProgressBar value={overall.value} className="max-w-xs" /> : null}
      </div>

      {evalAgg.hard_filter ? (
        <details className="rounded-md border border-amber-200 bg-amber-50/40 p-3" open>
          <summary className="cursor-pointer text-sm font-semibold text-amber-950">
            Hard Filter
          </summary>
          <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {Object.entries(evalAgg.hard_filter).map(([key, value]) => (
              <div key={key}>
                <dt className="text-xs text-amber-900/70">{formatFieldLabel(key)}</dt>
                <dd className="text-sm text-amber-950">{formatScalar(value)}</dd>
              </div>
            ))}
          </dl>
        </details>
      ) : null}

      {evalAgg.light ? <EvaluationMetaBlock label="Light Evaluation" block={evalAgg.light} /> : null}
      {evalAgg.deep ? <EvaluationMetaBlock label="Deep Evaluation" block={evalAgg.deep} /> : null}

      <div className="space-y-8 border-t border-slate-100 pt-6">
        {LAYER_SECTIONS.map(({ key, title, source }) => (
          <LayerBlock
            key={key}
            title={title}
            layer={active?.[key] as ScoreLayerEvaluation | undefined}
            criteriaFromScores={criteriaBySource(source)}
          />
        ))}
      </div>

      {scores.context_version != null || scores.stale != null ? (
        <dl className="grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 text-sm">
          <div>
            <dt className="text-xs text-slate-500">Context Version</dt>
            <dd>{formatScalar(scores.context_version)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Stale</dt>
            <dd>{formatScalar(scores.stale)}</dd>
          </div>
        </dl>
      ) : null}
    </section>
  )
}
