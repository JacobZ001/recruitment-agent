import { useState } from 'react'
import { addTag, removeTag, type TagValidationError } from '@/lib/scoringContextFormSchemas'

type TagInputProps = {
  label: string
  example: string
  tags: string[]
  onChange: (next: string[]) => void
  required?: boolean
}

export function TagInput({ label, example, tags, onChange }: TagInputProps) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<TagValidationError | null>(null)

  const onAdd = () => {
    const res = addTag(tags, draft)
    setError(res.error)
    if (!res.error) {
      onChange(res.next)
      setDraft('')
    }
  }

  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-slate-800">{label}</label>
      <p className="text-xs italic text-slate-500">
        <span className="font-medium not-italic">Example:</span> {example}
      </p>
      <div className="flex flex-wrap gap-2">
        <input
          className="min-w-[14rem] flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add A Tag"
        />
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
          onClick={onAdd}
        >
          Add
        </button>
      </div>
      {error ? (
        <p className="text-xs font-medium text-red-700" role="alert">
          {error.message}
        </p>
      ) : null}
      {tags.length > 0 ? (
        <ul className="mt-2 flex flex-wrap gap-2">
          {tags.map((t) => (
            <li key={t} className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs">
              <span className="text-slate-800">{t}</span>
              <button
                type="button"
                className="rounded-full px-1 text-slate-500 hover:bg-slate-200 hover:text-slate-800"
                aria-label={`Remove ${t}`}
                onClick={() => onChange(removeTag(tags, t))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

