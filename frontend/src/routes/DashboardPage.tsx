import { Link } from 'react-router-dom'
import { ProgressBar } from '../components/ProgressStepper'
import { JobStatusBadge } from '../components/StatusBadge'
import { NewspaperIcon, UploadCloudIcon } from '../components/icons'
import { useJobs } from '../features/jobs/useJobs'

const ACTIVE_STATUSES = new Set([
  'UPLOADED',
  'TEXT_EXTRACTION',
  'CHUNKING_SUMMARIZATION',
  'HIGHLIGHT_DETECTION',
  'REVIEW_DRAFTING',
])

function formatDate(value: string) {
  return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export default function DashboardPage() {
  const { data: jobs, isLoading, isError } = useJobs()

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="page-title">Revues de presse</h1>
          <p className="page-subtitle">Suivez la génération de vos revues, du téléversement à l&apos;export.</p>
        </div>
        <Link to="/upload" className="btn-primary shrink-0">
          <UploadCloudIcon className="h-4 w-4" />
          Nouvelle revue
        </Link>
      </div>

      <div className="mt-6 space-y-3">
        {isLoading &&
          [0, 1, 2].map((i) => (
            <div key={i} className="card h-[74px] animate-pulse bg-slate-50" />
          ))}
        {isError && (
          <div className="card border-red-200 bg-red-50 text-sm text-red-700">
            Impossible de charger les revues.
          </div>
        )}
        {jobs && jobs.length === 0 && (
          <div className="card flex flex-col items-center gap-3 py-12 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <NewspaperIcon className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-800">Aucune revue pour l&apos;instant</p>
              <p className="mt-1 text-sm text-slate-500">
                Commencez par{' '}
                <Link to="/upload" className="font-medium text-brand-600 hover:text-brand-700">
                  téléverser un PDF ou une photo
                </Link>
                .
              </p>
            </div>
          </div>
        )}
        {jobs?.map((job) => {
          const isActive = ACTIVE_STATUSES.has(job.status)
          return (
            <Link key={job.id} to={`/jobs/${job.id}`} className="card-interactive block">
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-slate-400">
                  <NewspaperIcon className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-900">{job.title || 'Revue sans titre'}</p>
                  <p className="mt-0.5 text-xs text-slate-500">{formatDate(job.created_at)}</p>
                </div>
                <JobStatusBadge status={job.status} />
              </div>
              {isActive && (
                <div className="mt-3 pl-14">
                  <ProgressBar percent={job.progress_percent} />
                </div>
              )}
            </Link>
          )
        })}
      </div>
    </div>
  )
}
