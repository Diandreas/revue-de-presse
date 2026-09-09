import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useParams } from 'react-router-dom'
import { extractErrorMessage } from '../api/client'
import { ProgressBar, ProgressStepper } from '../components/ProgressStepper'
import { JobStatusBadge } from '../components/StatusBadge'
import { useExportReview, useJob, useJobHighlights, useJobReview, useRetryJob } from '../features/jobs/useJobs'
import type { CategoryType } from '../api/types'

const READY_STATUSES = new Set(['REVIEW_READY', 'EXPORTED'])

const CATEGORY_FILTERS: { value: CategoryType | 'all'; label: string }[] = [
  { value: 'all', label: 'Tout' },
  { value: 'legal_risk', label: 'Risque juridique' },
  { value: 'important_point', label: 'Point important' },
  { value: 'intox', label: 'Intox potentielle' },
  { value: 'custom', label: 'Autre' },
]

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const { data: job, isLoading } = useJob(jobId)
  const isReady = Boolean(job && READY_STATUSES.has(job.status))
  const { data: highlights } = useJobHighlights(jobId, isReady)
  const { data: review } = useJobReview(jobId, isReady)
  const retryMutation = useRetryJob(jobId ?? '')
  const exportMutation = useExportReview(jobId ?? '')
  const [categoryFilter, setCategoryFilter] = useState<CategoryType | 'all'>('all')
  const [exportError, setExportError] = useState<string | null>(null)

  if (isLoading || !job) {
    return <p className="text-sm text-slate-500">Chargement…</p>
  }

  const filteredHighlights = highlights?.filter((h) => categoryFilter === 'all' || h.category.type === categoryFilter)

  const handleExport = async (format: 'pdf' | 'docx') => {
    setExportError(null)
    try {
      const url = await exportMutation.mutateAsync(format)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (error) {
      setExportError(extractErrorMessage(error, "Échec de l'export."))
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">{job.title || 'Revue sans titre'}</h1>
          <p className="mt-1 text-sm text-slate-500">{job.documents.length} document(s) source</p>
        </div>
        <JobStatusBadge status={job.status} />
      </div>

      {job.status === 'FAILED' ? (
        <div className="card mt-6 border-red-200 bg-red-50">
          <p className="text-sm font-medium text-red-800">La génération a échoué.</p>
          {job.error_message && <p className="mt-1 text-sm text-red-700">{job.error_message}</p>}
          <button
            type="button"
            className="btn-primary mt-4"
            disabled={retryMutation.isPending}
            onClick={() => retryMutation.mutate()}
          >
            {retryMutation.isPending ? 'Relance…' : 'Réessayer'}
          </button>
        </div>
      ) : !isReady ? (
        <div className="card mt-6">
          <div className="mb-4">
            <ProgressBar percent={job.progress_percent} />
            <p className="mt-1 text-right text-xs text-slate-500">{job.progress_percent}%</p>
          </div>
          <ProgressStepper steps={job.step_runs} />
        </div>
      ) : (
        <div className="mt-6 space-y-6">
          <div className="card">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-slate-900">Revue générée</h2>
              <div className="flex gap-2">
                <button type="button" className="btn-secondary" onClick={() => void handleExport('pdf')}>
                  Exporter en PDF
                </button>
                <button type="button" className="btn-secondary" onClick={() => void handleExport('docx')}>
                  Exporter en DOCX
                </button>
              </div>
            </div>
            {exportError && <p className="mt-2 text-sm text-red-600">{exportError}</p>}
            <div className="markdown-content mt-4">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{review?.summary_markdown ?? ''}</ReactMarkdown>
            </div>
          </div>

          <div className="card">
            <h2 className="text-sm font-semibold text-slate-900">Points saillants détectés</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {CATEGORY_FILTERS.map((filter) => (
                <button
                  key={filter.value}
                  type="button"
                  onClick={() => setCategoryFilter(filter.value)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    categoryFilter === filter.value
                      ? 'border-brand-500 bg-brand-50 text-brand-700'
                      : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {filter.label}
                </button>
              ))}
            </div>

            <ul className="mt-4 space-y-3">
              {filteredHighlights?.length === 0 && (
                <p className="text-sm text-slate-500">Aucun point saillant dans cette catégorie.</p>
              )}
              {filteredHighlights?.map((highlight) => (
                <li
                  key={highlight.id}
                  className="rounded-lg border border-slate-200 py-2 pl-4 pr-3"
                  style={{ borderLeftWidth: 4, borderLeftColor: highlight.category.color }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: highlight.category.color }}>
                      {highlight.category.name}
                    </span>
                    {highlight.page_number && (
                      <span className="text-xs text-slate-400">page {highlight.page_number}</span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-slate-800">{highlight.excerpt}</p>
                  {highlight.explanation && <p className="mt-1 text-xs text-slate-500">{highlight.explanation}</p>}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
