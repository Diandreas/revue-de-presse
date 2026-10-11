import clsx from 'clsx'

type Tone = 'slate' | 'brand' | 'amber' | 'green' | 'red'

const TONE_CLASSES: Record<Tone, string> = {
  slate: 'bg-slate-100 text-slate-600 ring-slate-200',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200/70',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200/70',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200/70',
  red: 'bg-red-50 text-red-700 ring-red-200/70',
}

const DOT_CLASSES: Record<Tone, string> = {
  slate: 'bg-slate-400',
  brand: 'bg-brand-500',
  amber: 'bg-amber-500',
  green: 'bg-emerald-500',
  red: 'bg-red-500',
}

const JOB_STATUS_LABELS: Record<string, { label: string; tone: Tone; pulse?: boolean }> = {
  UPLOADED: { label: 'En file d’attente', tone: 'slate', pulse: true },
  TEXT_EXTRACTION: { label: 'Lecture des documents', tone: 'brand', pulse: true },
  CHUNKING_SUMMARIZATION: { label: 'Résumé des articles', tone: 'brand', pulse: true },
  HIGHLIGHT_DETECTION: { label: 'Détection des points clés', tone: 'brand', pulse: true },
  REVIEW_DRAFTING: { label: 'Rédaction de la revue', tone: 'brand', pulse: true },
  REVIEW_READY: { label: 'Revue prête', tone: 'green' },
  EXPORTED: { label: 'Exportée', tone: 'green' },
  FAILED: { label: 'Échec', tone: 'red' },
}

const SUBSCRIPTION_STATUS_LABELS: Record<string, { label: string; tone: Tone }> = {
  trialing: { label: 'Essai gratuit', tone: 'brand' },
  active: { label: 'Active', tone: 'green' },
  past_due: { label: 'À renouveler', tone: 'amber' },
  canceled: { label: 'Résiliée', tone: 'red' },
  incomplete: { label: 'En attente d’activation', tone: 'amber' },
}

const INVOICE_STATUS_LABELS: Record<string, { label: string; tone: Tone }> = {
  pending: { label: 'À régler', tone: 'amber' },
  pending_review: { label: 'Justificatif en vérification', tone: 'brand' },
  paid: { label: 'Payée', tone: 'green' },
  failed: { label: 'Annulée', tone: 'red' },
  refunded: { label: 'Remboursée', tone: 'slate' },
}

export function Badge({ label, tone, pulse, className }: { label: string; tone: Tone; pulse?: boolean; className?: string }) {
  return (
    <span className={clsx('chip ring-1 ring-inset', TONE_CLASSES[tone], className)}>
      <span className="relative flex h-1.5 w-1.5">
        {pulse && <span className={clsx('absolute inline-flex h-full w-full animate-ping rounded-full opacity-60', DOT_CLASSES[tone])} />}
        <span className={clsx('relative inline-flex h-1.5 w-1.5 rounded-full', DOT_CLASSES[tone])} />
      </span>
      {label}
    </span>
  )
}

export function JobStatusBadge({ status, className }: { status: string; className?: string }) {
  const entry = JOB_STATUS_LABELS[status] ?? { label: status, tone: 'slate' as Tone }
  return <Badge label={entry.label} tone={entry.tone} pulse={entry.pulse} className={className} />
}

export function SubscriptionStatusBadge({ status }: { status: string }) {
  const entry = SUBSCRIPTION_STATUS_LABELS[status] ?? { label: status, tone: 'slate' as Tone }
  return <Badge label={entry.label} tone={entry.tone} />
}

export function InvoiceStatusBadge({ status }: { status: string }) {
  const entry = INVOICE_STATUS_LABELS[status] ?? { label: status, tone: 'slate' as Tone }
  return <Badge label={entry.label} tone={entry.tone} />
}
