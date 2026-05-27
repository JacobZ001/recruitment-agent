export type RecruiterActionLike = {
  group: string
  order: number
  label: string
  event_type: string
}

/** Deterministic ordering then stable grouping (order, label, event_type). */
export function actionsByGroup<T extends RecruiterActionLike>(
  actions: T[],
): { group: string; actions: T[] }[] {
  const sorted = [...actions].sort((a, b) => {
    if (a.order !== b.order) return a.order - b.order
    const byLabel = a.label.localeCompare(b.label)
    if (byLabel !== 0) return byLabel
    return a.event_type.localeCompare(b.event_type)
  })
  const groupOrder: string[] = []
  const by = new Map<string, T[]>()
  for (const a of sorted) {
    const g = a.group?.trim() ? a.group : 'other'
    if (!by.has(g)) {
      by.set(g, [])
      groupOrder.push(g)
    }
    by.get(g)!.push(a)
  }
  return groupOrder.map((g) => ({ group: g, actions: by.get(g)! }))
}
