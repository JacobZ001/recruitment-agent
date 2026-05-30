import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { CandidateGovernanceFlags, DedupMatch } from '@/api/types'
import { keepSeparateCandidateDedup, linkCandidateDedup } from '@/api/client'

type CandidateGovernancePanelProps = {
  candidateId: string
  flags: CandidateGovernanceFlags | undefined
  dedupMatches?: DedupMatch[]
  onResolved?: () => void
}

export function CandidateGovernancePanel({
  candidateId,
  flags,
  dedupMatches,
  onResolved,
}: CandidateGovernancePanelProps) {
  const [targetId, setTargetId] = useState('')
  const [reason, setReason] = useState('')
  const [actorId, setActorId] = useState('recruiter-ui')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!flags) return null
  const showDedup =
    flags.dedup_pending_resolution ||
    flags.dedup_status === 'suspected_duplicate' ||
    flags.orphan_ingress
  if (!showDedup && !flags.dedup_status) return null

  const submitLink = async () => {
    setBusy(true)
    setError(null)
    try {
      await linkCandidateDedup(candidateId, targetId.trim(), actorId.trim(), reason.trim())
      onResolved?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Link failed')
    } finally {
      setBusy(false)
    }
  }

  const submitKeep = async () => {
    setBusy(true)
    setError(null)
    try {
      await keepSeparateCandidateDedup(candidateId, actorId.trim(), reason.trim())
      onResolved?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Keep separate failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-2 rounded-md border border-amber-200 bg-amber-50/60 p-3 text-sm">
      <div className="flex flex-wrap gap-2">
        {flags.orphan_ingress && (
          <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-950">
            orphan ingress
          </span>
        )}
        {flags.dedup_status && (
          <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-900">
            dedup: {flags.dedup_status}
          </span>
        )}
        {flags.dedup_linked_to_candidate_id && (
          <Link
            className="text-xs text-indigo-700 hover:underline"
            to={`/candidates/${flags.dedup_linked_to_candidate_id}`}
          >
            linked → {flags.dedup_linked_to_candidate_id.slice(0, 8)}…
          </Link>
        )}
      </div>
      {flags.dedup_pending_resolution && (
        <div className="mt-3 space-y-2">
          <p className="text-xs text-amber-950">Resolve duplicate suspicion (no auto-merge):</p>
          {dedupMatches && dedupMatches.length > 0 && (
            <ul className="list-inside list-disc text-xs text-slate-700">
              {dedupMatches.map((m) => (
                <li key={m.candidate_id}>
                  <Link className="text-indigo-700 hover:underline" to={`/candidates/${m.candidate_id}`}>
                    {m.full_name || m.candidate_id}
                  </Link>{' '}
                  ({m.match_kinds.join(', ')})
                </li>
              ))}
            </ul>
          )}
          <input
            className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
            placeholder="Target candidate ID to link"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
          />
          <input
            className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
            placeholder="Reason (required)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <input
            className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
            placeholder="Actor ID"
            value={actorId}
            onChange={(e) => setActorId(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || !targetId.trim() || !reason.trim()}
              className="rounded bg-indigo-600 px-2 py-1 text-xs text-white disabled:opacity-50"
              onClick={() => void submitLink()}
            >
              Link to existing
            </button>
            <button
              type="button"
              disabled={busy || !reason.trim()}
              className="rounded border border-slate-300 bg-white px-2 py-1 text-xs disabled:opacity-50"
              onClick={() => void submitKeep()}
            >
              Keep separate
            </button>
          </div>
        </div>
      )}
      {error && (
        <p className="mt-2 text-xs text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
