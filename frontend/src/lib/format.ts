const dateTimeFormatter = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
const dateFormatter = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long' })
const shortDateFormatter = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' })
const relativeFormatter = new Intl.RelativeTimeFormat('fr-FR', { numeric: 'auto' })
const numberFormatter = new Intl.NumberFormat('fr-FR')

export function formatDateTime(value: string | null | undefined) {
  return value ? dateTimeFormatter.format(new Date(value)) : '—'
}

export function formatDate(value: string | null | undefined) {
  return value ? dateFormatter.format(new Date(value)) : '—'
}

export function formatShortDate(value: string | null | undefined) {
  return value ? shortDateFormatter.format(new Date(value)) : '—'
}

/** « il y a 5 minutes », « hier », « dans 3 jours »… */
export function formatRelative(value: string | null | undefined, now = Date.now()) {
  if (!value) return '—'
  const diffSeconds = Math.round((new Date(value).getTime() - now) / 1000)
  const abs = Math.abs(diffSeconds)
  if (abs < 45) return 'à l’instant'
  if (abs < 3600) return relativeFormatter.format(Math.round(diffSeconds / 60), 'minute')
  if (abs < 86400) return relativeFormatter.format(Math.round(diffSeconds / 3600), 'hour')
  if (abs < 86400 * 7) return relativeFormatter.format(Math.round(diffSeconds / 86400), 'day')
  return formatDate(value)
}

/** Nombre de jours entiers restants avant `value` (0 si dépassé). */
export function daysUntil(value: string | null | undefined, now = Date.now()) {
  if (!value) return 0
  return Math.max(0, Math.ceil((new Date(value).getTime() - now) / 86400000))
}

export function formatAmount(amount: string | number, currency: string) {
  return `${numberFormatter.format(Number(amount))} ${currency === 'XAF' ? 'FCFA' : currency}`
}

export function formatNumber(value: number) {
  return numberFormatter.format(value)
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`
}

/** plural(3, 'document') -> « 3 documents » ; plural(1, 'photo') -> « 1 photo ». */
export function plural(count: number, singular: string, pluralForm = `${singular}s`) {
  return `${formatNumber(count)} ${count > 1 ? pluralForm : singular}`
}

export function initialsOf(text: string | null | undefined) {
  if (!text) return '?'
  const parts = text.trim().split(/[\s@._-]+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

export function firstNameOf(fullName: string | null | undefined) {
  return fullName?.trim().split(/\s+/)[0] ?? ''
}

/** Couleur hex -> rgba (pour les teintes de fond dérivées de la couleur d'une catégorie). */
export function hexToRgba(hex: string, alpha: number) {
  const clean = hex.replace('#', '')
  const full = clean.length === 3 ? clean.split('').map((c) => c + c).join('') : clean.padEnd(6, '0').slice(0, 6)
  const value = Number.parseInt(full, 16)
  if (Number.isNaN(value)) return `rgba(100, 116, 139, ${alpha})`
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`
}
