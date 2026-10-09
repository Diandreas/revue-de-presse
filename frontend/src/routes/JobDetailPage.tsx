import clsx from 'clsx'
import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useParams } from 'react-router-dom'
import { extractErrorMessage } from '../api/client'
import type { CategoryType, Highlight, PressReviewJobDetail, SourceDocument } from '../api/types'
import { DocumentGrid } from '../components/DocumentGrid'
import { PressReviewSheet, pressReviewToText } from '../components/PressReviewSheet'
import { PIPELINE_STEPS, ProgressStepper } from '../components/ProgressStepper'
import { JobStatusBadge } from '../components/StatusBadge'
import { useToast } from '../components/Toast'
import {
  AlertTriangleIcon,
  ClockIcon,
  DownloadIcon,
  FileTextIcon,
  HighlighterIcon,
  ImageIcon,
  LayersIcon,
  NewspaperIcon,
  RefreshIcon,
  ScaleIcon,
  SparkleIcon,
  StarIcon,
  TagIcon,
  type IconComponent,
} from '../components/icons'
import { Alert, CopyButton, EmptyState, FullPageLoader, PageHeader, ProgressRing, Segmented, Skeleton, Spinner } from '../components/ui'
import {
  ACTIVE_STATUSES,
  READY_STATUSES,
  useExportReview,
  useJob,
  useJobHighlights,
  useJobReview,
  useRetryJob,
} from '../features/jobs/useJobs'
import { formatDateTime, formatRelative, hexToRgba, plural } from '../lib/format'

const CATEGORY_ICONS: Record<CategoryType, IconComponent> = {
  legal_risk: ScaleIcon,
  important_point: StarIcon,
  intox: AlertTriangleIcon,
  custom: TagIcon,
}

function slugify(text: string) {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80)
}

function documentSummary(documents: SourceDocument[]) {
  const images = documents.filter((d) => d.kind === 'image').length
  const pdfs = documents.length - images
  const parts = []
  if (images) parts.push(plural(images, 'photo'))
  if (pdfs) parts.push(plural(pdfs, 'PDF', 'PDF'))
  return parts.join(' · ')
}

/* ---------------------------------------------------------------------------
 * Analyse en cours
 * ------------------------------------------------------------------------- */

function ProcessingPanel({ job }: { job: PressReviewJobDetail }) {
  const runningIndex = PIPELINE_STEPS.findIndex(
    (definition) => job.step_runs.find((s) => s.step_name === definition.name)?.status === 'running',
  )
  const current = runningIndex >= 0 ? PIPELINE_STEPS[runningIndex] : null
  const queuedForLong =
    job.status === 'UPLOADED' && Date.now() - new Date(job.created_at).getTime() > 2 * 60 * 1000

  return (
    <section className="card overflow-hidden !p-0">
      <div className="relative flex flex-col items-center gap-6 bg-gradient-to-br from-brand-50 via-white to-amber-50/40 px-6 py-8 text-center sm:flex-row sm:px-8 sm:text-left">
        <ProgressRing percent={job.progress_percent} size={128} stroke={11}>
          <span className="font-display text-3xl font-semibold text-slate-900 tabular-nums">{job.progress_percent}%</span>
          <span className="text-[11px] text-slate-500">terminé</span>
        </ProgressRing>
        <div className="min-w-0">
          <JobStatusBadge status={job.status} />
          <h2 className="mt-3 font-display text-2xl font-semibold text-slate-900">
            {job.status === 'UPLOADED' ? 'Analyse sur le point de démarrer…' : 'Analyse en cours…'}
          </h2>
          <p className="mt-1.5 max-w-lg text-sm leading-relaxed text-slate-600">
            {current
              ? `Étape ${runningIndex + 1} sur ${PIPELINE_STEPS.length} : ${current.label.toLowerCase()}. `
              : ''}
            Vous pouvez fermer cette page : l’analyse continue sur nos serveurs et la revue apparaîtra dans votre
            tableau de bord dès qu’elle sera prête.
          </p>
          {job.started_at && (
            <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-slate-400">
              <ClockIcon className="h-3.5 w-3.5" />
              Démarrée {formatRelative(job.started_at)}
            </p>
          )}
        </div>
      </div>
      {queuedForLong && (
        <div className="border-t border-slate-100 px-6 pt-5 sm:px-8">
          <Alert tone="info">
            Le démarrage prend plus de temps que d’habitude : l’analyse commencera automatiquement dès qu’un serveur
            sera disponible. Inutile de relancer.
          </Alert>
        </div>
      )}
      <div className="border-t border-slate-100 px-6 py-7 sm:px-8">
        <ProgressStepper steps={job.step_runs} />
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------------------
 * Revue prête
 * ------------------------------------------------------------------------- */

function HighlightCard({ highlight, sourceName }: { highlight: Highlight; sourceName?: string }) {
  const color = highlight.category.color || '#64748b'
  const Icon = CATEGORY_ICONS[highlight.category.type] ?? TagIcon
  return (
    <article
      className="rounded-2xl border bg-white p-4 shadow-[var(--shadow-soft)] animate-slide-up"
      style={{ borderColor: hexToRgba(color, 0.28) }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="chip" style={{ backgroundColor: hexToRgba(color, 0.1), color }}>
          <Icon className="h-3.5 w-3.5" />
          {highlight.category.name}
        </span>
        {highlight.confidence != null && (
          <span className="text-[11px] text-slate-400 tabular-nums" title="Niveau de confiance de l’IA">
            Confiance {Math.round(highlight.confidence * 100)} %
          </span>
        )}
      </div>
      <blockquote
        className="mt-3 rounded-r-lg py-1.5 pr-2 pl-3 font-display text-[15px] leading-relaxed text-slate-900 italic"
        style={{ borderLeft: `3px solid ${color}`, backgroundColor: hexToRgba(color, 0.05) }}
      >
        {/* Espaces insécables : les guillemets ne passent jamais seuls à la ligne. */}
        {`« ${highlight.excerpt.trim()} »`}
      </blockquote>
      {highlight.explanation && <p className="mt-2.5 text-[13px] leading-relaxed text-slate-600">{highlight.explanation}</p>}
      {sourceName && (
        <p className="mt-3 flex items-center gap-1.5 text-[11px] text-slate-400">
          <FileTextIcon className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">
            {sourceName}
            {highlight.page_number ? ` · page ${highlight.page_number}` : ''}
          </span>
        </p>
      )}
    </article>
  )
}

function HighlightsPanel({ highlights, documents }: { highlights: Highlight[] | undefined; documents: SourceDocument[] }) {
  const [filter, setFilter] = useState<string>('all')
  const documentNames = useMemo(() => new Map(documents.map((d) => [d.id, d.original_filename])), [documents])

  const categories = useMemo(() => {
    const byId = new Map<string, { id: string; name: string; color: string; count: number }>()
    for (const highlight of highlights ?? []) {
      const entry = byId.get(highlight.category.id)
      if (entry) entry.count += 1
      else
        byId.set(highlight.category.id, {
          id: highlight.category.id,
          name: highlight.category.name,
          color: highlight.category.color,
          count: 1,
        })
    }
    return [...byId.values()]
  }, [highlights])

  const visible = highlights?.filter((h) => filter === 'all' || h.category.id === filter)

  return (
    <section className="card !p-0">
      <div className="border-b border-slate-100 px-5 pt-5 pb-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="section-title flex items-center gap-2">
            <HighlighterIcon className="h-5 w-5 text-amber-500" />
            Points clés
          </h2>
          {highlights && <span className="text-xs font-medium text-slate-400">{highlights.length}</span>}
        </div>
        {categories.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setFilter('all')}
              className={clsx(
                'chip ring-1 transition',
                filter === 'all' ? 'bg-ink-900 text-white ring-ink-900' : 'bg-white text-slate-600 ring-slate-200 hover:ring-slate-300',
              )}
            >
              Tous · {highlights?.length ?? 0}
            </button>
            {categories.map((category) => (
              <button
                key={category.id}
                type="button"
                onClick={() => setFilter(category.id)}
                className="chip ring-1 transition"
                style={
                  filter === category.id
                    ? { backgroundColor: category.color, color: '#fff', boxShadow: `0 0 0 1px ${category.color}` }
                    : { backgroundColor: hexToRgba(category.color, 0.08), color: category.color, boxShadow: `0 0 0 1px ${hexToRgba(category.color, 0.25)}` }
                }
              >
                {category.name} · {category.count}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="scrollbar-thin space-y-3 p-4 lg:max-h-[calc(100vh-12rem)] lg:overflow-y-auto">
        {!highlights &&
          [0, 1, 2].map((i) => (
            <div key={i} className="space-y-2 rounded-2xl border border-slate-100 p-4">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-4/5" />
            </div>
          ))}
        {highlights && highlights.length === 0 && (
          <EmptyState
            icon={HighlighterIcon}
            title="Aucun point clé"
            description="L’IA n’a repéré aucun passage correspondant à vos catégories de détection dans ces documents."
            className="!py-8"
          />
        )}
        {visible?.map((highlight) => (
          <HighlightCard
            key={highlight.id}
            highlight={highlight}
            sourceName={highlight.source_document ? documentNames.get(highlight.source_document) : undefined}
          />
        ))}
      </div>
    </section>
  )
}

type ReadyTab = 'review' | 'highlights' | 'documents'

/* ---------------------------------------------------------------------------
 * Page
 * ------------------------------------------------------------------------- */

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const toast = useToast()
  const { data: job, isLoading, isError } = useJob(jobId)
  const isReady = Boolean(job && READY_STATUSES.has(job.status))
  const isActive = Boolean(job && ACTIVE_STATUSES.has(job.status))
  const { data: highlights } = useJobHighlights(jobId, isReady)
  const { data: review, isLoading: reviewLoading } = useJobReview(jobId, isReady)
  const retryMutation = useRetryJob(jobId ?? '')
  const exportMutation = useExportReview(jobId ?? '')
  const [tab, setTab] = useState<ReadyTab>('review')

  if (isLoading) return <FullPageLoader label="Chargement de la revue…" />
  if (isError || !job) {
    return (
      <EmptyState
        icon={NewspaperIcon}
        title="Revue introuvable"
        description="Cette revue n’existe pas ou n’appartient pas à votre organisation."
      />
    )
  }

  const skipped = job.documents.filter((d) => d.extraction_status === 'failed')
  const exportingFormat = exportMutation.isPending ? exportMutation.variables : null

  const handleExport = async (format: 'pdf' | 'docx') => {
    try {
      const url = await exportMutation.mutateAsync(format)
      // Lien de téléchargement direct (même origine) : pas bloqué comme une pop-up sur mobile.
      const link = document.createElement('a')
      link.href = url
      link.download = `${slugify(job.title || 'revue-de-presse') || 'revue-de-presse'}.${format}`
      link.rel = 'noopener'
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (error) {
      toast.error(extractErrorMessage(error, 'L’export a échoué. Réessayez dans un instant.'))
    }
  }

  const handleRetry = async () => {
    try {
      await retryMutation.mutateAsync()
      toast.success('Analyse relancée.')
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible de relancer l’analyse.'))
    }
  }

  const meta = (
    <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
      <span className="inline-flex items-center gap-1.5">
        <ClockIcon className="h-4 w-4" />
        {formatDateTime(job.created_at)}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <LayersIcon className="h-4 w-4" />
        {documentSummary(job.documents) || plural(job.documents.length, 'document')}
      </span>
      {isReady && highlights && (
        <span className="inline-flex items-center gap-1.5">
          <HighlighterIcon className="h-4 w-4 text-amber-500" />
          {plural(highlights.length, 'point clé', 'points clés')}
        </span>
      )}
    </span>
  )

  const exportActions = isReady && (
    <>
      {review?.summary_markdown && (
        <CopyButton
          text={review.structured ? pressReviewToText(review.structured) : review.summary_markdown}
          label="Copier le texte"
          className="!h-10 !px-4"
        />
      )}
      <button type="button" className="btn-secondary" disabled={exportMutation.isPending} onClick={() => void handleExport('docx')}>
        {exportingFormat === 'docx' ? <Spinner /> : <DownloadIcon className="h-4 w-4" />}
        Word
      </button>
      <button type="button" className="btn-primary" disabled={exportMutation.isPending} onClick={() => void handleExport('pdf')}>
        {exportingFormat === 'pdf' ? <Spinner /> : <DownloadIcon className="h-4 w-4" />}
        Exporter en PDF
      </button>
    </>
  )

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/dashboard', label: 'Revues de presse' }}
        eyebrow={<JobStatusBadge status={job.status} className="normal-case tracking-normal" />}
        title={job.title || 'Revue sans titre'}
        subtitle={meta}
        actions={exportActions || undefined}
      />

      {isActive && (
        <>
          <ProcessingPanel job={job} />
          <section>
            <h2 className="section-title mb-4">Documents analysés</h2>
            <DocumentGrid documents={job.documents} processing />
          </section>
        </>
      )}

      {job.status === 'FAILED' && (
        <>
          <Alert
            tone="danger"
            title="L’analyse n’a pas pu aboutir"
            action={
              <button type="button" className="btn-primary" disabled={retryMutation.isPending} onClick={() => void handleRetry()}>
                {retryMutation.isPending ? <Spinner /> : <RefreshIcon className="h-4 w-4" />}
                {retryMutation.isPending ? 'Relance…' : 'Relancer l’analyse'}
              </button>
            }
          >
            {job.error_message || 'Une erreur inattendue est survenue.'} Les documents déjà lus ne seront pas relus.
          </Alert>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <section className="card">
              <h2 className="section-title mb-5">Déroulement</h2>
              <ProgressStepper steps={job.step_runs} />
            </section>
            <section className="card">
              <h2 className="section-title mb-4">Documents</h2>
              <DocumentGrid documents={job.documents} />
            </section>
          </div>
        </>
      )}

      {isReady && (
        <>
          {skipped.length > 0 && (
            <Alert tone="warning" title={`${plural(skipped.length, 'fichier')} non lu${skipped.length > 1 ? 's' : ''}`}>
              {skipped.map((d) => d.original_filename).join(', ')} {skipped.length > 1 ? 'n’ont' : 'n’a'} pas pu être lu
              {skipped.length > 1 ? 's' : ''} (photo floue ou fichier illisible) et {skipped.length > 1 ? 'ne figurent' : 'ne figure'} donc
              pas dans la revue.
            </Alert>
          )}

          <Segmented
            className="w-full lg:hidden"
            value={tab}
            onChange={setTab}
            options={[
              { value: 'review', label: 'Revue' },
              { value: 'highlights', label: `Points clés${highlights ? ` · ${highlights.length}` : ''}` },
              { value: 'documents', label: `Documents · ${job.documents.length}` },
            ]}
          />

          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
            <article className={clsx('min-w-0 overflow-hidden rounded-3xl border border-slate-200/80 bg-paper shadow-[var(--shadow-card)]', tab !== 'review' && 'hidden lg:block')}>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/70 px-6 py-4 sm:px-10">
                <p className="eyebrow !text-slate-500">Revue de presse · {formatDateTime(review?.generated_at ?? job.completed_at)}</p>
                <span className="chip bg-brand-50 text-brand-700 ring-1 ring-brand-200/70">
                  <SparkleIcon className="h-3.5 w-3.5" />
                  Rédigée par l’IA
                </span>
              </div>
              <div className="px-6 py-8 sm:px-10 sm:py-10">
                {reviewLoading && (
                  <div className="space-y-3">
                    <Skeleton className="h-8 w-2/3" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-4/5" />
                  </div>
                )}
                {review?.structured && <PressReviewSheet review={review.structured} />}
                {review && !review.structured && (
                  <div className="prose-review">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{review.summary_markdown}</ReactMarkdown>
                  </div>
                )}
              </div>
              <p className="border-t border-slate-200/70 px-6 py-4 text-xs leading-relaxed text-slate-400 sm:px-10">
                Synthèse générée automatiquement à partir des documents fournis. Elle ne constitue pas un avis juridique :
                vérifiez les passages sensibles avant diffusion.
              </p>
            </article>

            <div className={clsx('lg:sticky lg:top-8', tab !== 'highlights' && 'hidden lg:block')}>
              <HighlightsPanel highlights={highlights} documents={job.documents} />
            </div>
          </div>

          <section className={clsx(tab !== 'documents' && 'hidden lg:block')}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="section-title">Documents source</h2>
              <span className="text-xs text-slate-400">
                <ImageIcon className="mr-1 inline h-3.5 w-3.5" />
                Cliquez pour ouvrir l’original
              </span>
            </div>
            <DocumentGrid documents={job.documents} />
          </section>
        </>
      )}
    </div>
  )
}
