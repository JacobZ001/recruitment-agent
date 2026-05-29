import { useState } from 'react'

const MAX_CHARS = 280

export function ExpandableText({ text, className = '' }: { text: string; className?: string }) {
  const [expanded, setExpanded] = useState(false)
  const trimmed = text.trim()
  if (!trimmed) return null
  const long = trimmed.length > MAX_CHARS
  const shown = long && !expanded ? `${trimmed.slice(0, MAX_CHARS)}…` : trimmed
  return (
    <div className={className}>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{shown}</p>
      {long ? (
        <button
          type="button"
          className="mt-1 text-xs font-medium text-indigo-700 hover:underline"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      ) : null}
    </div>
  )
}
