import clsx from 'clsx'

type Tone = 'slate' | 'blue' | 'amber' | 'green' | 'red'

const TONE_CLASSES: Record<Tone, string> = {
  slate: 'bg-slate-100 text-slate-700',
  blue: 'bg-blue-100 text-blue-700',
  amber: 'bg-amber-100 text-amber-800',
  green: 'bg-green-100 text-green-700',
  red: 'bg-red-100 text-red-700',
}

const JOB_STATUS_LABELS: Record<string, { label: string; tone: Tone }> = {
  UPLOADED: { label: 'Téléversé', tone: 'slate' },
  TEXT_EXTRACTION: { label: 'Extraction du texte', tone: 'blue' },
  CHUNKING_SUMMARIZATION: { label: 'Découpage & résumé', tone: 'blue' },
  HIGHLIGHT_DETECTION: { label: 'Détection des points saillants', tone: 'blue' },
  REVIEW_DRAFTING: { label: 'Rédaction de la revue', tone: 'blue' },
  REVIEW_READY: { label: 'Revue prête', tone: 'green' },
  EXPORTED: { label: 'Exportée', tone: 'green' },
  FAILED: { label: 'Échec', tone: 'red' },
}

const SUBSCRIPTION_STATUS_LABELS: Record<string, { label: string; tone: Tone }> = {
  trialing: { label: 'Essai', tone: 'blue' },
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

function Badge({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={clsx('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', TONE_CLASSES[tone])}>
      {label}
    </span>
  )
}

export function JobStatusBadge({ status }: { status: string }) {
  const entry = JOB_STATUS_LABELS[status] ?? { label: status, tone: 'slate' as Tone }
  return <Badge label={entry.label} tone={entry.tone} />
}

export function SubscriptionStatusBadge({ status }: { status: string }) {
  const entry = SUBSCRIPTION_STATUS_LABELS[status] ?? { label: status, tone: 'slate' as Tone }
  return <Badge label={entry.label} tone={entry.tone} />
}

export function InvoiceStatusBadge({ status }: { status: string }) {
  const entry = INVOICE_STATUS_LABELS[status] ?? { label: status, tone: 'slate' as Tone }
  return <Badge label={entry.label} tone={entry.tone} />
}
