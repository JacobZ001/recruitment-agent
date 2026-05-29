/** Display label: underscores removed, words capitalized; `Summary` stays as-is. */
export function formatFieldLabel(key: string): string {
  const normalized = key.trim()
  if (normalized.toLowerCase() === 'summary') return 'Summary'
  return normalized
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

export const NULL_DISPLAY = '— —'

/** Decimal score (0–1) → percent string without rounding beyond source precision. */
export function formatScorePercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return NULL_DISPLAY
  const raw = String(value)
  if (raw.includes('e') || raw.includes('E')) {
    return `${value * 100}%`
  }
  const negative = raw.startsWith('-')
  const abs = negative ? raw.slice(1) : raw
  const [intPart, fracPart = ''] = abs.split('.')
  if (!fracPart) {
    return `${negative ? '-' : ''}${intPart}00%`.replace(/^(-?)0+(\d)/, '$1$2')
  }
  const fracLen = fracPart.length
  const scale = Math.max(0, fracLen - 2)
  const digits = intPart + fracPart
  const pointPos = intPart.length + 2
  if (pointPos >= digits.length) {
    const padded = digits.padEnd(pointPos, '0')
    const whole = padded.slice(0, pointPos).replace(/^0+/, '') || '0'
    const rest = padded.slice(pointPos).replace(/0+$/, '')
    const body = rest ? `${whole}.${rest}` : whole
    return `${negative ? '-' : ''}${body}%`
  }
  const whole = digits.slice(0, pointPos).replace(/^0+/, '') || '0'
  let rest = digits.slice(pointPos)
  if (scale === 0) {
    return `${negative ? '-' : ''}${whole}%`
  }
  rest = rest.padEnd(scale, '0').slice(0, scale).replace(/0+$/, '')
  const body = rest ? `${whole}.${rest}` : whole
  return `${negative ? '-' : ''}${body}%`
}

export function formatScalar(value: unknown): string {
  if (value == null || value === '') return NULL_DISPLAY
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}
