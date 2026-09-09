import { Link } from 'react-router-dom'
import { ProgressBar } from '../components/ProgressStepper'
import { JobStatusBadge } from '../components/StatusBadge'
import { useJobs } from '../features/jobs/useJobs'

function formatDate(value: string) {
  return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export default function DashboardPage() {
  const { data: jobs, isLoading, isError } = useJobs()

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Revues de presse</h1>
          <p className="mt-1 text-sm text-slate-500">Suivez la génération de vos revues, du téléversement à l&apos;export.</p>
        </div>
        <Link to="/upload" className="btn-primary">
          Nouvelle revue
        </Link>
      </div>

      <div className="mt-6 space-y-3">
        {isLoading && <p className="text-sm text-slate-500">Chargement…</p>}
        {isError && <p className="text-sm text-red-600">Impossible de charger les revues.</p>}
        {jobs && jobs.length === 0 && (
          <div className="card text-center text-sm text-slate-500">
            Aucune revue pour l&apos;instant. Commencez par{' '}
            <Link to="/upload" className="font-medium text-brand-600 hover:text-brand-700">
              téléverser des PDF
            </Link>
            .
          </div>
        )}
        {jobs?.map((job) => (
          <Link key={job.id} to={`/jobs/${job.id}`} className="card block hover:border-brand-300">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">{job.title || 'Revue sans titre'}</p>
                <p className="mt-0.5 text-xs text-slate-500">{formatDate(job.created_at)}</p>
              </div>
              <JobStatusBadge status={job.status} />
            </div>
            {job.status !== 'REVIEW_READY' && job.status !== 'EXPORTED' && job.status !== 'FAILED' && (
              <div className="mt-3">
                <ProgressBar percent={job.progress_percent} />
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  )
}
