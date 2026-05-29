import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ApiRequestError, extractApiError, postCandidateAction } from '@/api/client'
import type { RecruiterActionItem } from '@/api/types'

type DialogState = { open: false } | { open: true; action: RecruiterActionItem }

export function useRecruiterActions(defaultCandidateId = '') {
  const queryClient = useQueryClient()
  const candidateIdRef = useRef(defaultCandidateId)
  useEffect(() => {
    if (defaultCandidateId) candidateIdRef.current = defaultCandidateId
  }, [defaultCandidateId])
  const [dialog, setDialog] = useState<DialogState>({ open: false })
  const [reason, setReason] = useState('')
  const [actorId, setActorId] = useState(
    () => import.meta.env.VITE_DEFAULT_ACTOR_ID ?? 'recruiter-spa',
  )
  const [formError, setFormError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async ({ eventType, payload }: { eventType: string; payload: Record<string, unknown> }) =>
      postCandidateAction(candidateIdRef.current, eventType, payload),
    onSuccess: async () => {
      const cid = candidateIdRef.current
      await queryClient.invalidateQueries({ queryKey: ['candidate', cid] })
      await queryClient.invalidateQueries({ queryKey: ['candidates'] })
      setDialog({ open: false })
      setReason('')
      setFormError(null)
    },
  })

  const openAction = (action: RecruiterActionItem, candidateId?: string) => {
    if (candidateId) {
      candidateIdRef.current = candidateId
    } else if (defaultCandidateId) {
      candidateIdRef.current = defaultCandidateId
    }
    setFormError(null)
    setReason('')
    setActorId(import.meta.env.VITE_DEFAULT_ACTOR_ID ?? 'recruiter-spa')
    setDialog({ open: true, action })
  }

  const submitAction = async () => {
    if (!dialog.open) return
    if (!candidateIdRef.current) {
      setFormError('Candidate id is missing.')
      return
    }
    const r = reason.trim()
    if (r.length < 1) {
      setFormError('Reason is required (min 1 character).')
      return
    }
    const aid = actorId.trim()
    if (aid.length < 1) {
      setFormError('Actor id is required.')
      return
    }
    setFormError(null)
    try {
      await mutation.mutateAsync({
        eventType: dialog.action.event_type,
        payload: {
          actor_id: aid,
          actor_type: 'recruiter',
          reason: r,
          evidence_refs: [],
        },
      })
    } catch (e) {
      if (e instanceof ApiRequestError) {
        const parsed = extractApiError(e.body)
        setFormError(parsed?.code ? `${parsed.code}: ${parsed.message ?? ''}` : e.message)
      } else {
        setFormError(e instanceof Error ? e.message : 'Request failed')
      }
    }
  }

  return {
    dialog,
    setDialog,
    reason,
    setReason,
    actorId,
    setActorId,
    formError,
    openAction,
    submitAction,
    mutation,
  }
}
