import clsx from 'clsx'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { PressReviewJobListItem } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { JobStatusBadge } from '../components/StatusBadge'
import { UsageBanner } from '../components/UsageCard'
import {
  AlertCircleIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  ChevronRightIcon,
  ClockIcon,
  DownloadIcon,
  FileTextIcon,
  HighlighterIcon,
  LayersIcon,
  NewspaperIcon,
  PlusIcon,
  SparkleIcon,
  UploadCloudIcon,
} from '../components/icons'
import { Alert, PageHeader, ProgressBar, Skeleton, StatCard } from '../components/ui'
import { usageStateOf } from '../features/billing/usage'
import { useSubscription } from '../features/billing/useBilling'
import { ACTIVE_STATUSES, useJobStats, useJobs } from '../features/jobs/useJobs'
import { firstNameOf, formatNumber, formatRelative, plural } from '../lib/format'

const STEP_HINTS: Record<string, string> = {
  UPLOADED: 'En attente de démarrage…',
  TEXT_EXTRACTION: 'Lecture des documents',
  CHUNKING_SUMMARIZATION: 'Résumé des articles',
  HIGHLIGHT_DETECTION: 'Détection des points clés',
  REVIEW_DRAFTING: 'Rédaction de la revue',
}

function todayLabel() {
  const label = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function JobRow({ job }: { job: PressReviewJobListItem }) {
  const isActive = ACTIVE_STATUSES.has(job.status)
  const isFailed = job.status === 'FAILED'
  const isReady = job.status === 'REVIEW_READY' || job.status === 'EXPORTED'

  return (
    <Link to={`/jobs/${job.id}`} className="card-interactive group flex items-center gap-4 animate-slide-up">
      <div
        className={clsx(
          'flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl',
          isReady && 'bg-emerald-50 text-emerald-600',
          isActive && 'bg-brand-50 text-brand-600',
          isFailed && 'bg-red-50 text-red-600',
        )}
      >
        {isReady && <CheckCircleIcon className="h-6 w-6" />}
        {isActive && <SparkleIcon className="h-6 w-6 animate-pulse" />}
        {isFailed && <AlertCircleIcon className="h-6 w-6" />}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <p className="truncate font-display text-[16px] font-semibold text-slate-900 group-hover:text-brand-700">
            {job.title || 'Revue sans titre'}
          </p>
          <JobStatusBadge status={job.status} className="hidden shrink-0 sm:inline-flex" />
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1">
            <ClockIcon className="h-3.5 w-3.5" />
            {formatRelative(job.created_at)}
          </span>
          <span className="inline-flex items-center gap-1">
            <LayersIcon className="h-3.5 w-3.5" />
            {plural(job.documents_count, 'document')}
          </span>
          {isReady && (
            <span className="inline-flex items-center gap-1 font-medium text-slate-600">
              <HighlighterIcon className="h-3.5 w-3.5 text-amber-500" />
              {plural(job.highlights_count, 'point clé', 'points clés')}
            </span>
          )}
        </div>
        {isActive && (
          <div className="mt-3 flex items-center gap-3">
            <ProgressBar percent={job.progress_percent} size="sm" className="max-w-xs" />
            <span className="text-xs font-medium whitespace-nowrap text-brand-700 tabular-nums">
              {STEP_HINTS[job.status]} · {job.progress_percent} %
            </span>
          </div>
        )}
        <JobStatusBadge status={job.status} className="mt-2 sm:hidden" />
      </div>

      <ChevronRightIcon className="hidden h-5 w-5 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-brand-500 sm:block" />
    </Link>
  )
}

const HOW_IT_WORKS = [
  {
    icon: UploadCloudIcon,
    title: 'Déposez vos coupures',
    text: 'PDF ou photos prises au téléphone, une ou plusieurs à la fois.',
  },
  {
    icon: SparkleIcon,
    title: 'L’IA analyse en arrière-plan',
    text: 'Lecture, résumé et détection des risques juridiques, points clés et intox.',
  },
  {
    icon: DownloadIcon,
    title: 'Partagez la revue',
    text: 'Une revue rédigée et structurée, exportable en PDF ou en Word.',
  },
]

function OnboardingEmptyState() {
  return (
    <div className="card overflow-hidden !p-0">
      <div className="relative px-6 pt-10 pb-8 text-center sm:px-10">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-brand-50 to-transparent" />
        <div className="relative mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-[var(--shadow-card)] ring-1 ring-slate-200/80">
          <NewspaperIcon className="h-7 w-7" />
        </div>
        <h2 className="relative mt-5 font-display text-2xl font-semibold text-slate-900">
          Votre première revue de presse en <span className="highlighter">3 étapes</span>
        </h2>
        <p className="relative mx-auto mt-2 max-w-lg text-sm leading-relaxed text-slate-500">
          Déposez les articles du jour : nous nous occupons du reste, même si vous fermez la page.
        </p>
      </div>
      <ol className="grid gap-px border-t border-slate-100 bg-slate-100 sm:grid-cols-3">
        {HOW_IT_WORKS.map((step, index) => (
          <li key={step.title} className="bg-white p-6">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                <step.icon className="h-[18px] w-[18px]" />
              </span>
              <span className="eyebrow">Étape {index + 1}</span>
            </div>
            <p className="mt-4 text-sm font-semibold text-slate-900">{step.title}</p>
            <p className="mt-1 text-sm leading-relaxed text-slate-500">{step.text}</p>
          </li>
        ))}
      </ol>
      <div className="flex justify-center border-t border-slate-100 bg-slate-50/60 px-6 py-6">
        <Link to="/upload" className="btn-primary btn-lg">
          <PlusIcon className="h-[18px] w-[18px]" />
          Créer ma première revue
        </Link>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { user, organization } = useAuth()
  const [pageSize, setPageSize] = useState(20)
  const { data: jobsPage, isLoading, isError, isFetching } = useJobs(pageSize)
  const { data: stats } = useJobStats()
  const { data: subscription, isLoading: subscriptionLoading } = useSubscription()
  const usage = usageStateOf(subscription, subscriptionLoading)
  const jobs = jobsPage?.results
  const firstName = firstNameOf(user?.full_name)

  const quotaValue =
    usage.kind === 'trial' || usage.kind === 'active' ? (
      <>
        {usage.used}
        <span className="text-lg text-slate-400"> / {usage.limit}</span>
      </>
    ) : (
      '—'
    )

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={todayLabel()}
        title={firstName ? `Bonjour ${firstName}` : 'Bonjour'}
        subtitle={`Suivez les revues de presse de ${organization?.name ?? 'votre organisation'}, du dépôt des coupures jusqu’à l’export.`}
        actions={
          <Link to="/upload" className="btn-primary btn-lg w-full sm:w-auto">
            <PlusIcon className="h-[18px] w-[18px]" />
            Nouvelle revue
          </Link>
        }
      />

      <UsageBanner />

      <section className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard
          icon={FileTextIcon}
          label="Revues sur la période"
          value={quotaValue}
          hint={
            usage.kind === 'trial'
              ? `Essai gratuit · ${plural(usage.daysLeft, 'jour')} restant${usage.daysLeft > 1 ? 's' : ''}`
              : usage.kind === 'active'
                ? `Formule ${usage.planName}`
                : undefined
          }
        />
        <StatCard
          icon={SparkleIcon}
          label="En cours d’analyse"
          value={stats ? formatNumber(stats.active) : '—'}
          tone="amber"
          hint={stats?.active ? 'Mise à jour en direct' : 'Aucune analyse en cours'}
        />
        <StatCard
          icon={CheckCircleIcon}
          label="Revues prêtes"
          value={stats ? formatNumber(stats.ready) : '—'}
          tone="emerald"
          hint={stats ? `${plural(stats.documents, 'document analysé', 'documents analysés')}` : undefined}
        />
        <StatCard
          icon={HighlighterIcon}
          label="Points clés repérés"
          value={stats ? formatNumber(stats.highlights) : '—'}
          tone="rose"
          hint="Risques, points importants, intox"
        />
      </section>

      <section>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 className="section-title">Revues récentes</h2>
            <p className="mt-0.5 text-sm text-slate-500">L’analyse continue même si vous fermez cette page.</p>
          </div>
          {stats && stats.total > 0 && (
            <span className="hidden text-xs text-slate-400 sm:block">{plural(stats.total, 'revue')} au total</span>
          )}
        </div>

        {isError && <Alert tone="danger">Impossible de charger vos revues. Vérifiez votre connexion puis réessayez.</Alert>}

        <div className="space-y-3">
          {isLoading &&
            [0, 1, 2].map((i) => (
              <div key={i} className="card flex items-center gap-4 !p-5">
                <Skeleton className="h-12 w-12 rounded-2xl" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-3 w-1/3" />
                </div>
              </div>
            ))}
          {jobs?.map((job) => <JobRow key={job.id} job={job} />)}
        </div>

        {jobs && jobs.length === 0 && <OnboardingEmptyState />}

        {jobsPage?.next && (
          <div className="mt-5 flex justify-center">
            {pageSize < 100 ? (
              <button
                type="button"
                className="btn-secondary"
                disabled={isFetching}
                onClick={() => setPageSize((size) => Math.min(100, size + 20))}
              >
                Afficher plus de revues
                <ArrowRightIcon className="h-4 w-4 rotate-90" />
              </button>
            ) : (
              <p className="text-xs text-slate-400">Les 100 revues les plus récentes sont affichées.</p>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
