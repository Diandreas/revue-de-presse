import { useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import clsx from 'clsx'
import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useNavigate, useParams } from 'react-router-dom'
import { extractErrorMessage } from '../api/client'
import type {
  CategoryType,
  DetectionCategory,
  GeneratedReview,
  Highlight,
  PressReviewJobDetail,
  SourceDocument,
} from '../api/types'
import { DocumentGrid } from '../components/DocumentGrid'
import { JobActionsMenu } from '../components/JobActionsMenu'
import { Modal } from '../components/Modal'
import { PressReviewEditor } from '../components/PressReviewEditor'
import { PressReviewSheet, pressReviewToText } from '../components/PressReviewSheet'
import { PIPELINE_STEPS, ProgressStepper } from '../components/ProgressStepper'
import { ShareReviewButton } from '../components/ShareReviewButton'
import { JobStatusBadge } from '../components/StatusBadge'
import { useToast } from '../components/Toast'
import {
  AlertTriangleIcon,
  CheckIcon,
  ClockIcon,
  DownloadIcon,
  EyeIcon,
  EyeOffIcon,
  FileTextIcon,
  HighlighterIcon,
  ImageIcon,
  LayersIcon,
  NewspaperIcon,
  PenLineIcon,
  RefreshIcon,
  RotateCcwIcon,
  ScaleIcon,
  SparkleIcon,
  StarIcon,
  TagIcon,
  type IconComponent,
} from '../components/icons'
import { Alert, CopyButton, EmptyState, FullPageLoader, PageHeader, ProgressRing, Segmented, Skeleton, Spinner } from '../components/ui'
import { useCategories } from '../features/categories/useCategories'
import {
  countEntries,
  createDraft,
  draftChanges,
  draftProblems,
  draftToStructured,
  type ReviewDraft,
} from '../features/jobs/reviewDraft'
import {
  ACTIVE_STATUSES,
  READY_STATUSES,
  useExportReview,
  useJob,
  useJobHighlights,
  useJobReview,
  useRetryJob,
} from '../features/jobs/useJobs'
import { useRestoreReview, useUpdateHighlight, useUpdateReview } from '../features/jobs/useReviewEditing'
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

interface HighlightCardProps {
  highlight: Highlight
  sourceName?: string
  categories: DetectionCategory[]
  onToggleHidden: (highlight: Highlight) => void
  onChangeCategory: (highlight: Highlight, category: DetectionCategory) => void
}

function HighlightCard({ highlight, sourceName, categories, onToggleHidden, onChangeCategory }: HighlightCardProps) {
  const color = highlight.category.color || '#64748b'
  const Icon = CATEGORY_ICONS[highlight.category.type] ?? TagIcon
  // Catégories proposées : les actives, plus l'actuelle même si elle a été désactivée depuis.
  const choices = categories.some((c) => c.id === highlight.category.id) ? categories : [highlight.category, ...categories]
  return (
    <article
      className={clsx(
        'rounded-2xl border bg-white p-4 shadow-[var(--shadow-soft)] animate-slide-up',
        highlight.hidden && 'border-dashed !bg-slate-50 opacity-75',
      )}
      style={{ borderColor: hexToRgba(color, 0.28) }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="chip" style={{ backgroundColor: hexToRgba(color, 0.1), color }}>
          <Icon className="h-3.5 w-3.5" />
          {highlight.category.name}
        </span>
        <div className="flex items-center gap-1">
          {highlight.confidence != null && (
            <span className="text-[11px] text-slate-400 tabular-nums" title="Niveau de confiance de l’IA">
              Confiance {Math.round(highlight.confidence * 100)} %
            </span>
          )}
          <button
            type="button"
            className="btn-icon !h-8 !w-8"
            aria-pressed={highlight.hidden}
            aria-label={highlight.hidden ? 'Réafficher ce point clé' : 'Masquer ce point clé (faux positif)'}
            title={highlight.hidden ? 'Réafficher dans la revue et les exports' : 'Masquer : absent des exports PDF et Word'}
            onClick={() => onToggleHidden(highlight)}
          >
            {highlight.hidden ? <EyeIcon className="h-4 w-4" /> : <EyeOffIcon className="h-4 w-4" />}
          </button>
        </div>
      </div>
      {highlight.hidden && (
        <p className="mt-2 text-[11px] font-semibold tracking-wide text-slate-500 uppercase">Masqué · absent des exports</p>
      )}
      <blockquote
        className="mt-3 rounded-r-lg py-1.5 pr-2 pl-3 font-display text-[15px] leading-relaxed text-slate-900 italic"
        style={{ borderLeft: `3px solid ${color}`, backgroundColor: hexToRgba(color, 0.05) }}
      >
        {/* Espaces insécables : les guillemets ne passent jamais seuls à la ligne. */}
        {`« ${highlight.excerpt.trim()} »`}
      </blockquote>
      {highlight.explanation && <p className="mt-2.5 text-[13px] leading-relaxed text-slate-600">{highlight.explanation}</p>}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 text-[11px] text-slate-400">
        {sourceName ? (
          <p className="flex min-w-0 items-center gap-1.5">
            <FileTextIcon className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">
              {sourceName}
              {highlight.page_number ? ` · page ${highlight.page_number}` : ''}
            </span>
          </p>
        ) : (
          <span />
        )}
        {choices.length > 1 && (
          <select
            className="max-w-[11rem] rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] text-slate-600"
            aria-label="Changer la catégorie de ce point clé"
            value={highlight.category.id}
            onChange={(event) => {
              const category = choices.find((c) => c.id === event.target.value)
              if (category) onChangeCategory(highlight, category)
            }}
          >
            {choices.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        )}
      </div>
    </article>
  )
}

type HighlightFilter = 'all' | 'hidden' | string

function HighlightsPanel({
  highlights,
  documents,
  jobId,
}: {
  highlights: Highlight[] | undefined
  documents: SourceDocument[]
  jobId: string
}) {
  const toast = useToast()
  const [filter, setFilter] = useState<HighlightFilter>('all')
  const documentNames = useMemo(() => new Map(documents.map((d) => [d.id, d.original_filename])), [documents])
  const { data: allCategories } = useCategories()
  const activeCategories = useMemo(() => (allCategories ?? []).filter((c) => c.is_active), [allCategories])
  const updateHighlight = useUpdateHighlight(jobId)

  const shown = useMemo(() => highlights?.filter((h) => !h.hidden), [highlights])
  const hiddenCount = (highlights?.length ?? 0) - (shown?.length ?? 0)

  const categories = useMemo(() => {
    const byId = new Map<string, { id: string; name: string; color: string; count: number }>()
    for (const highlight of shown ?? []) {
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
  }, [shown])

  // Filtre devenu vide (dernier point d'une catégorie masqué, dernier masqué réaffiché) :
  // retour à la liste complète.
  const activeFilter: HighlightFilter =
    filter === 'hidden'
      ? hiddenCount > 0
        ? 'hidden'
        : 'all'
      : filter === 'all' || categories.some((c) => c.id === filter)
        ? filter
        : 'all'
  const visible =
    activeFilter === 'hidden'
      ? highlights?.filter((h) => h.hidden)
      : shown?.filter((h) => activeFilter === 'all' || h.category.id === activeFilter)

  const toggleHidden = (highlight: Highlight) => {
    const hidden = !highlight.hidden
    updateHighlight.mutate(
      { highlightId: highlight.id, hidden },
      {
        onSuccess: () =>
          toast.success(hidden ? 'Point clé masqué : il n’apparaîtra plus dans les exports.' : 'Point clé réaffiché.'),
        onError: (error) => toast.error(extractErrorMessage(error, 'Impossible de modifier ce point clé.')),
      },
    )
  }

  const changeCategory = (highlight: Highlight, category: DetectionCategory) => {
    updateHighlight.mutate(
      { highlightId: highlight.id, category },
      {
        onSuccess: () => toast.success(`Point clé classé dans « ${category.name} ».`),
        onError: (error) => toast.error(extractErrorMessage(error, 'Impossible de changer la catégorie.')),
      },
    )
  }

  return (
    <section className="card !p-0">
      <div className="border-b border-slate-100 px-5 pt-5 pb-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="section-title flex items-center gap-2">
            <HighlighterIcon className="h-5 w-5 text-amber-500" />
            Points clés
          </h2>
          {shown && <span className="text-xs font-medium text-slate-400">{shown.length}</span>}
        </div>
        {(categories.length > 0 || hiddenCount > 0) && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setFilter('all')}
              className={clsx(
                'chip ring-1 transition',
                activeFilter === 'all' ? 'bg-ink-900 text-white ring-ink-900' : 'bg-white text-slate-600 ring-slate-200 hover:ring-slate-300',
              )}
            >
              Tous · {shown?.length ?? 0}
            </button>
            {categories.map((category) => (
              <button
                key={category.id}
                type="button"
                onClick={() => setFilter(category.id)}
                className="chip ring-1 transition"
                style={
                  activeFilter === category.id
                    ? { backgroundColor: category.color, color: '#fff', boxShadow: `0 0 0 1px ${category.color}` }
                    : { backgroundColor: hexToRgba(category.color, 0.08), color: category.color, boxShadow: `0 0 0 1px ${hexToRgba(category.color, 0.25)}` }
                }
              >
                {category.name} · {category.count}
              </button>
            ))}
            {hiddenCount > 0 && (
              <button
                type="button"
                onClick={() => setFilter('hidden')}
                className={clsx(
                  'chip ring-1 transition',
                  activeFilter === 'hidden'
                    ? 'bg-slate-600 text-white ring-slate-600'
                    : 'bg-slate-50 text-slate-500 ring-slate-200 hover:ring-slate-300',
                )}
              >
                <EyeOffIcon className="h-3.5 w-3.5" />
                Masqués · {hiddenCount}
              </button>
            )}
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
        {highlights && highlights.length > 0 && visible?.length === 0 && (
          <p className="px-2 py-6 text-center text-sm text-slate-500">
            Tous les points clés sont masqués. Ouvrez « Masqués » pour en réafficher.
          </p>
        )}
        {visible?.map((highlight) => (
          <HighlightCard
            key={highlight.id}
            highlight={highlight}
            sourceName={
              highlight.source_name ??
              (highlight.source_document ? documentNames.get(highlight.source_document) : undefined)
            }
            categories={activeCategories}
            onToggleHidden={toggleHidden}
            onChangeCategory={changeCategory}
          />
        ))}
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------------------
 * Relecture : mode « Modifier » de la revue
 * ------------------------------------------------------------------------- */

const NO_PROBLEMS = new Map<string, string>()

/** État du mode « Modifier » : brouillon local, enregistrement optimiste (la revue corrigée
 * s'affiche aussitôt ; en cas d'échec, l'éditeur se rouvre avec le brouillon intact). */
function useReviewEditor(job: PressReviewJobDetail, review: GeneratedReview | undefined) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const updateReview = useUpdateReview(job.id)
  const restoreReview = useRestoreReview(job.id)
  const [editor, setEditor] = useState<{ draft: ReviewDraft; initial: ReviewDraft } | null>(null)
  const [editing, setEditing] = useState(false)
  const [showProblems, setShowProblems] = useState(false)

  const dirty = Boolean(editing && editor && Object.keys(draftChanges(editor.draft, editor.initial)).length > 0)

  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const start = () => {
    if (!review?.structured) return
    const initial = createDraft(review.structured, review.rubriques, job.title)
    setEditor({ draft: initial, initial })
    setShowProblems(false)
    setEditing(true)
  }

  const cancel = () => {
    setEditing(false)
    setEditor(null)
  }

  const change = (update: (draft: ReviewDraft) => ReviewDraft) =>
    setEditor((current) => (current ? { ...current, draft: update(current.draft) } : current))

  const save = () => {
    if (!editor || !review) return
    const { first } = draftProblems(editor.draft)
    if (first) {
      setShowProblems(true)
      toast.error(first)
      return
    }
    const changes = draftChanges(editor.draft, editor.initial)
    if (Object.keys(changes).length === 0) {
      cancel()
      toast.info('Aucune modification à enregistrer.')
      return
    }
    setEditing(false)
    updateReview.mutate(
      {
        changes: { ...changes, expected_edited_at: review.edited_at },
        optimistic: draftToStructured(editor.draft, review.rubriques, review.structured?.country ?? ''),
      },
      {
        onSuccess: () => {
          setEditor(null)
          toast.success('Revue enregistrée. Les exports PDF et Word reprennent vos corrections.')
        },
        onError: (error) => {
          setEditing(true)
          if (isAxiosError(error) && error.response?.status === 409) {
            // Version à jour rechargée : un nouvel « Enregistrer » remplacera la correction du collègue.
            void queryClient.invalidateQueries({ queryKey: ['jobs', job.id, 'review'] })
          }
          toast.error(extractErrorMessage(error, 'L’enregistrement a échoué. Vos modifications sont conservées : réessayez.'))
        },
      },
    )
  }

  const restore = async () => {
    try {
      await restoreReview.mutateAsync()
      cancel()
      toast.success('Version rédigée par l’IA restaurée.')
      return true
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible de restaurer la version de l’IA.'))
      return false
    }
  }

  return {
    editing: editing && editor !== null,
    draft: editor?.draft ?? null,
    dirty,
    problems: showProblems && editor ? draftProblems(editor.draft).byEntry : NO_PROBLEMS,
    saving: updateReview.isPending,
    restoring: restoreReview.isPending,
    start,
    cancel,
    change,
    save,
    restore,
  }
}

type ReviewEditorState = ReturnType<typeof useReviewEditor>

function ReviewArticle({
  job,
  review,
  reviewLoading,
  editor,
  className,
}: {
  job: PressReviewJobDetail
  review: GeneratedReview | undefined
  reviewLoading: boolean
  editor: ReviewEditorState
  className?: string
}) {
  const [restoreOpen, setRestoreOpen] = useState(false)
  const canEdit = Boolean(review?.structured)

  return (
    <article
      className={clsx(
        // overflow-clip (et non hidden) : la barre « Enregistrer » reste collée en bas de l'écran.
        'min-w-0 overflow-clip rounded-3xl border bg-paper shadow-[var(--shadow-card)]',
        editor.editing ? 'border-brand-300 ring-2 ring-brand-100' : 'border-slate-200/80',
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/70 px-6 py-4 sm:px-10">
        <p className="eyebrow !text-slate-500">
          {editor.editing ? 'Modification de la revue' : `Revue de presse · ${formatDateTime(review?.generated_at ?? job.completed_at)}`}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {review?.is_edited ? (
            <span className="chip bg-amber-50 text-amber-800 ring-1 ring-amber-200/70" title="Corrigée à la main après la rédaction par l’IA">
              <PenLineIcon className="h-3.5 w-3.5" />
              Corrigée{review.edited_by_name ? ` par ${review.edited_by_name}` : ''}
              {review.edited_at ? ` · ${formatRelative(review.edited_at)}` : ''}
            </span>
          ) : (
            <span className="chip bg-brand-50 text-brand-700 ring-1 ring-brand-200/70">
              <SparkleIcon className="h-3.5 w-3.5" />
              Rédigée par l’IA
            </span>
          )}
          {canEdit && !editor.editing && (
            <>
              {review?.is_edited && (
                <button type="button" className="btn-ghost btn-sm" disabled={editor.saving} onClick={() => setRestoreOpen(true)}>
                  <RotateCcwIcon className="h-4 w-4" />
                  Version de l’IA
                </button>
              )}
              <button type="button" className="btn-secondary btn-sm" disabled={editor.saving} onClick={editor.start}>
                {editor.saving ? <Spinner /> : <PenLineIcon className="h-4 w-4" />}
                {editor.saving ? 'Enregistrement…' : 'Modifier'}
              </button>
            </>
          )}
        </div>
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
        {editor.editing && editor.draft && review ? (
          <PressReviewEditor
            draft={editor.draft}
            onChange={editor.change}
            rubriques={review.rubriques}
            country={review.structured?.country ?? ''}
            problems={editor.problems}
          />
        ) : (
          <>
            {review?.structured && <PressReviewSheet review={review.structured} />}
            {review && !review.structured && (
              <div className="prose-review">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{review.summary_markdown}</ReactMarkdown>
              </div>
            )}
          </>
        )}
      </div>

      {editor.editing && editor.draft ? (
        <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-white/95 px-6 py-3 backdrop-blur sm:px-10">
          <p className="text-xs text-slate-500">
            {plural(countEntries(editor.draft), 'notice')} · {editor.dirty ? 'modifications non enregistrées' : 'aucune modification'}
          </p>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={editor.cancel}>
              Annuler
            </button>
            <button type="button" className="btn-primary" onClick={editor.save}>
              <CheckIcon className="h-4 w-4" />
              Enregistrer
            </button>
          </div>
        </div>
      ) : (
        <p className="border-t border-slate-200/70 px-6 py-4 text-xs leading-relaxed text-slate-400 sm:px-10">
          Synthèse générée automatiquement à partir des documents fournis. Elle ne constitue pas un avis juridique :
          vérifiez les passages sensibles avant diffusion.
        </p>
      )}

      <Modal
        open={restoreOpen}
        onClose={() => setRestoreOpen(false)}
        title="Restaurer la version de l’IA ?"
        description="La revue redevient celle rédigée par l’IA : toutes les corrections manuelles (notices, ordre, date) sont perdues."
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setRestoreOpen(false)}>
              Annuler
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={editor.restoring}
              onClick={() => void editor.restore().then((ok) => ok && setRestoreOpen(false))}
            >
              {editor.restoring ? <Spinner /> : <RotateCcwIcon className="h-4 w-4" />}
              Restaurer
            </button>
          </>
        }
      >
        <p className="text-sm text-slate-600">Le titre de la revue et les points clés masqués ne changent pas.</p>
      </Modal>
    </article>
  )
}

type ReadyTab = 'review' | 'highlights' | 'documents'

/* ---------------------------------------------------------------------------
 * Page
 * ------------------------------------------------------------------------- */

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const { data: job, isLoading, isError } = useJob(jobId)

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
  return <JobDetail key={job.id} job={job} />
}

function JobDetail({ job }: { job: PressReviewJobDetail }) {
  const toast = useToast()
  const navigate = useNavigate()
  const isReady = READY_STATUSES.has(job.status)
  const isActive = ACTIVE_STATUSES.has(job.status)
  const { data: highlights } = useJobHighlights(job.id, isReady)
  const { data: review, isLoading: reviewLoading } = useJobReview(job.id, isReady)
  const retryMutation = useRetryJob(job.id)
  const exportMutation = useExportReview(job.id)
  const [tab, setTab] = useState<ReadyTab>('review')
  const editor = useReviewEditor(job, review)

  const skipped = job.documents.filter((d) => d.extraction_status === 'failed')
  const exportingFormat = exportMutation.isPending ? exportMutation.variables : null
  const shownHighlights = highlights?.filter((h) => !h.hidden)
  const fileBase = slugify(job.title || 'revue-de-presse') || 'revue-de-presse'
  const reviewText = review ? (review.structured ? pressReviewToText(review.structured) : review.summary_markdown) : ''
  // Tout ce qui change le PDF : titre, corrections, points clés masqués ou reclassés.
  const exportVersion = [
    job.title,
    review?.edited_at ?? review?.generated_at ?? '',
    (highlights ?? []).map((h) => `${h.id}:${h.hidden ? 1 : 0}:${h.category.id}`).join(','),
  ].join('|')

  const handleExport = async (format: 'pdf' | 'docx') => {
    try {
      const url = await exportMutation.mutateAsync(format)
      // Lien de téléchargement direct (même origine) : pas bloqué comme une pop-up sur mobile.
      const link = document.createElement('a')
      link.href = url
      link.download = `${fileBase}.${format}`
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

  const startEditing = () => {
    editor.start()
    setTab('review')
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
      {isReady && shownHighlights && (
        <span className="inline-flex items-center gap-1.5">
          <HighlighterIcon className="h-4 w-4 text-amber-500" />
          {plural(shownHighlights.length, 'point clé', 'points clés')}
        </span>
      )}
    </span>
  )

  const actions = (
    <>
      {isReady && !editor.editing && (
        <>
          {reviewText && <CopyButton text={reviewText} label="Copier le texte" className="!h-10 !px-4" />}
          {reviewText && (
            <ShareReviewButton
              title={job.title || 'Revue de presse'}
              text={reviewText}
              fileName={`${fileBase}.pdf`}
              getPdfUrl={() => exportMutation.mutateAsync('pdf')}
              version={exportVersion}
              onDownloadPdf={() => void handleExport('pdf')}
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
      )}
      <JobActionsMenu job={job} onDeleted={() => navigate('/dashboard')} />
    </>
  )

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/dashboard', label: 'Revues de presse' }}
        eyebrow={<JobStatusBadge status={job.status} className="normal-case tracking-normal" />}
        title={job.title || 'Revue sans titre'}
        subtitle={meta}
        actions={actions}
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
              { value: 'highlights', label: `Points clés${shownHighlights ? ` · ${shownHighlights.length}` : ''}` },
              { value: 'documents', label: `Documents · ${job.documents.length}` },
            ]}
          />

          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
            <ReviewArticle
              job={job}
              review={review}
              reviewLoading={reviewLoading}
              editor={{ ...editor, start: startEditing }}
              className={clsx(tab !== 'review' && 'hidden lg:block')}
            />

            <div className={clsx('lg:sticky lg:top-8', tab !== 'highlights' && 'hidden lg:block')}>
              <HighlightsPanel highlights={highlights} documents={job.documents} jobId={job.id} />
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
