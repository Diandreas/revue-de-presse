import clsx from 'clsx'
import type { PipelineStepRun } from '../api/types'

const STEP_LABELS: Record<string, string> = {
  TEXT_EXTRACTION: 'Extraction du texte',
  CHUNKING_SUMMARIZATION: 'Découpage & résumé',
  HIGHLIGHT_DETECTION: 'Détection des points saillants',
  REVIEW_DRAFTING: 'Rédaction de la revue',
}

const STEP_ORDER = Object.keys(STEP_LABELS)

function stepStatusFor(steps: PipelineStepRun[], stepName: string) {
  return steps.find((s) => s.step_name === stepName)
}

export function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
      <div
        className="h-full rounded-full bg-brand-500 transition-all duration-500"
        style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
      />
    </div>
  )
}

export function ProgressStepper({ steps }: { steps: PipelineStepRun[] }) {
  return (
    <ol className="space-y-4">
      {STEP_ORDER.map((stepName, index) => {
        const step = stepStatusFor(steps, stepName)
        const status = step?.status ?? 'pending'
        return (
          <li key={stepName} className="flex items-start gap-3">
            <div
              className={clsx(
                'mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
                status === 'succeeded' && 'bg-green-500 text-white',
                status === 'running' && 'bg-brand-500 text-white',
                status === 'failed' && 'bg-red-500 text-white',
                status === 'pending' && 'bg-slate-200 text-slate-500',
              )}
            >
              {status === 'succeeded' ? '✓' : index + 1}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-slate-800">{STEP_LABELS[stepName]}</p>
                {status === 'running' && <span className="text-xs text-slate-500">{step?.progress_percent ?? 0}%</span>}
              </div>
              {status === 'running' && (
                <div className="mt-1.5">
                  <ProgressBar percent={step?.progress_percent ?? 0} />
                </div>
              )}
              {status === 'failed' && step?.error_message && (
                <p className="mt-1 text-xs text-red-600">{step.error_message}</p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
