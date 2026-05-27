import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listCandidates } from '@/api/client'
import { LIST_DISPLAY_LIMIT } from '@/lib/constants'

export function CandidateListPage() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['candidates'],
    queryFn: listCandidates,
  })

  const [stageFilter, setStageFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  const stageOptions = useMemo(() => {
    if (!data) return ['all']
    const s = new Set(data.map((r) => r.stage))
    return ['all', ...[...s].sort()]
  }, [data])

  const filtered = useMemo(() => {
    if (!data) return []
    return data.filter((row) => {
      if (stageFilter !== 'all' && row.stage !== stageFilter) return false
      if (statusFilter !== 'all' && row.status.kind !== statusFilter) return false
      return true
    })
  }, [data, stageFilter, statusFilter])

  const capped = useMemo(() => filtered.slice(0, LIST_DISPLAY_LIMIT), [filtered])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Candidates</h1>
        <p className="mt-1 text-sm text-slate-600">
          Showing up to {LIST_DISPLAY_LIMIT} rows after client filters (full list from API; see{' '}
          <code className="rounded bg-slate-100 px-1 text-xs">TD-API-005</code>).
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-700">Stage</span>
          <select
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 shadow-sm"
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
          >
            {stageOptions.map((o) => (
              <option key={o} value={o}>
                {o === 'all' ? 'All stages' : o}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-700">Status</span>
          <select
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 shadow-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="active">active</option>
            <option value="inactive">inactive</option>
            <option value="hired">hired</option>
          </select>
        </label>
        <p className="text-sm text-slate-500">
          {filtered.length} match · displaying {capped.length}
          {data ? ` of ${data.length} total from API` : ''}
        </p>
      </div>

      {isPending && (
        <div
          className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-600"
          role="status"
        >
          Loading candidates…
        </div>
      )}

      {isError && (
        <div
          className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"
          role="alert"
        >
          {error instanceof Error ? error.message : 'Failed to load candidates'}
        </div>
      )}

      {!isPending && !isError && capped.length === 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-slate-600">
          No candidates match these filters.
        </div>
      )}

      {!isPending && !isError && capped.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="sticky top-0 z-10 bg-slate-100">
                <tr>
                  <th className="px-4 py-3 font-semibold text-slate-700">Rank</th>
                  <th className="px-4 py-3 font-semibold text-slate-700">Candidate</th>
                  <th className="px-4 py-3 font-semibold text-slate-700">Stage</th>
                  <th className="px-4 py-3 font-semibold text-slate-700">Status</th>
                  <th className="px-4 py-3 font-semibold text-slate-700">Score</th>
                  <th className="px-4 py-3 font-semibold text-slate-700">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {capped.map((row) => (
                  <tr key={row.candidate_id} className="hover:bg-slate-50/80">
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {row.rank ?? '—'}
                      {row.total_candidates != null ? (
                        <span className="text-xs text-slate-400"> / {row.total_candidates}</span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/candidates/${row.candidate_id}`}
                        className="font-medium text-indigo-700 hover:underline"
                      >
                        {row.candidate_id}
                      </Link>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{row.stage}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{row.status.kind}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                      {row.overall_score?.value != null ? (
                        <>
                          {row.overall_score.value.toFixed(2)}
                          {row.overall_score.type ? (
                            <span className="ml-1 rounded bg-slate-100 px-1.5 text-xs text-slate-600">
                              {row.overall_score.type}
                            </span>
                          ) : null}
                        </>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {row.available_actions?.length ?? 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
