import clsx from 'clsx'

type Tone = 'slate' | 'brand' | 'amber' | 'green' | 'red'

const TONE_CLASSES: Record<Tone, string> = {
  slate: 'bg-slate-100 text-slate-600',
  brand: 'bg-brand-50 text-brand-700',
  amber: 'bg-amber-50 text-amber-700',
  green: 'bg-emerald-50 text-emerald-700',
  red: 'bg-red-50 text-red-700',
}

const DOT_CLASSES: Record<Tone, string> = {
  slate: 'bg-slate-400',
  brand: 'bg-brand-500',
  amber: 'bg-amber-500',
  green: 'bg-emerald-500',
  red: 'bg-red-500',
}

const JOB_STATUS_LABELS: Record<string, { label: string; tone: Tone; pulse?: boolean }> = {
  UPLOADED: { label: 'Téléversé', tone: 'slate' },
  TEXT_EXTRACTION: { label: 'Extraction du texte', tone: 'brand', pulse: true },
  CHUNKING_SUMMARIZATION: { label: 'Découpage & résumé', tone: 'brand', pulse: true },
  HIGHLIGHT_DETECTION: { label: 'Détection des points saillants', tone: 'brand', pulse: true },
  REVIEW_DRAFTING: { label: 'Rédaction de la revue', tone: 'brand', pulse: true },
  REVIEW_READY: { label: 'Revue prête', tone: 'green' },
  EXPORTED: { label: 'Exportée', tone: 'green' },
  FAILED: { label: 'Échec', tone: 'red' },
}

const SUBSCRIPTION_STATUS_LABELS: Record<string, { label: string; tone: Tone }> = {
  trialing: { label: 'Essai', tone: 'brand' },
  active: { label: 'Active', tone: 'green' },
  past_due: { label: 'En retard', tone: 'amber' },
  canceled: { label: 'Annulée', tone: 'red' },
  incomplete: { label: 'Incomplète', tone: 'slate' },
}

const INVOICE_STATUS_LABELS: Record<string, { label: string; tone: Tone }> = {
  pending: { label: 'En attente', tone: 'amber' },
  pending_review: { label: 'Justificatif à valider', tone: 'amber' },
  paid: { label: 'Payée', tone: 'green' },
  failed: { label: 'Échouée', tone: 'red' },
  refunded: { label: 'Remboursée', tone: 'slate' },
}

function Badge({ label, tone, pulse }: { label: string; tone: Tone; pulse?: boolean }) {
  return (
    <span className={clsx('chip', TONE_CLASSES[tone])}>
      <span className={clsx('h-1.5 w-1.5 rounded-full', DOT_CLASSES[tone], pulse && 'animate-pulse')} />
      {label}
    </span>
  )
}

export function JobStatusBadge({ status }: { status: string }) {
  const entry = JOB_STATUS_LABELS[status] ?? { label: status, tone: 'slate' as Tone }
  return <Badge label={entry.label} tone={entry.tone} pulse={entry.pulse} />
}

export function SubscriptionStatusBadge({ status }: { status: string }) {
  const entry = SUBSCRIPTION_STATUS_LABELS[status] ?? { label: status, tone: 'slate' as Tone }
  return <Badge label={entry.label} tone={entry.tone} />
}

export function InvoiceStatusBadge({ status }: { status: string }) {
  const entry = INVOICE_STATUS_LABELS[status] ?? { label: status, tone: 'slate' as Tone }
  return <Badge label={entry.label} tone={entry.tone} />
}
