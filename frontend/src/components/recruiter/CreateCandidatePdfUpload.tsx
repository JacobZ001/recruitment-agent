import { Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { createCandidateWithPdf } from '@/api/client'

type CreateCandidatePdfUploadProps = {
  contextReady: boolean
}

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `idem-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function CreateCandidatePdfUpload({ contextReady }: CreateCandidatePdfUploadProps) {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const idempotencyKeyRef = useRef<string | null>(null)
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastCandidateId, setLastCandidateId] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async (file: File) => {
      const key = idempotencyKeyRef.current
      if (!key) throw new Error('No idempotency key for upload session')
      const buf = await file.arrayBuffer()
      const bytes = new Uint8Array(buf)
      let binary = ''
      for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]!)
      const pdf_base64 = btoa(binary)
      return createCandidateWithPdf({
        pdf_base64,
        file_name: file.name,
        idempotencyKey: key,
      })
    },
    onSuccess: (data) => {
      setLastCandidateId(data.candidate_id)
      setError(null)
      void queryClient.invalidateQueries({ queryKey: ['candidates'] })
    },
    onError: (e) => {
      setError(e instanceof Error ? e.message : 'Upload failed')
    },
  })

  const onPickFile = () => {
    if (!contextReady) return
    fileInputRef.current?.click()
  }

  const onFileChange = (file: File | null) => {
    if (!file) return
    idempotencyKeyRef.current = newIdempotencyKey()
    setSelectedName(file.name)
    setError(null)
    mutation.mutate(file)
  }

  const onNewUploadSession = () => {
    idempotencyKeyRef.current = null
    setSelectedName(null)
    setError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const retrySameFile = () => {
    const input = fileInputRef.current
    const file = input?.files?.[0]
    if (!file || !idempotencyKeyRef.current) return
    mutation.mutate(file)
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">Create candidate (PDF)</h2>
      <p className="mt-1 text-sm text-slate-600">
        One-step create + CV upload. Requires scoring context{' '}
        <code className="rounded bg-slate-100 px-1 text-xs">ready</code>.
      </p>
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
      />
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!contextReady || mutation.isPending}
          onClick={onPickFile}
        >
          {mutation.isPending ? 'Uploading…' : 'Upload PDF to create candidate'}
        </button>
        {selectedName && idempotencyKeyRef.current && (
          <button
            type="button"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            disabled={mutation.isPending}
            onClick={retrySameFile}
          >
            Retry same file
          </button>
        )}
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
          onClick={onNewUploadSession}
        >
          New upload session
        </button>
      </div>
      {selectedName && (
        <p className="mt-2 text-xs text-slate-500">
          File: {selectedName}
          {idempotencyKeyRef.current ? ` · idempotency key fixed for this session` : ''}
        </p>
      )}
      {lastCandidateId && (
        <p className="mt-2 text-sm text-green-800">
          Created candidate{' '}
          <Link className="font-medium text-indigo-700 hover:underline" to={`/candidates/${lastCandidateId}`}>
            {lastCandidateId}
          </Link>
        </p>
      )}
      {error && (
        <p className="mt-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
