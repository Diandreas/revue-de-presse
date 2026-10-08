import clsx from 'clsx'
import type { PipelineStepRun } from '../api/types'
import {
  AlertCircleIcon,
  CheckIcon,
  ClockIcon,
  HighlighterIcon,
  PenLineIcon,
  ScanTextIcon,
  SparkleIcon,
  type IconComponent,
} from './icons'
import { ProgressBar } from './ui'

export const PIPELINE_STEPS: { name: string; label: string; description: string; icon: IconComponent }[] = [
  {
    name: 'TEXT_EXTRACTION',
    label: 'Lecture des documents',
    description: 'Le texte des PDF est extrait ; les photos sont lues par l’IA.',
    icon: ScanTextIcon,
  },
  {
    name: 'CHUNKING_SUMMARIZATION',
    label: 'Résumé des articles',
    description: 'Chaque article est découpé puis résumé.',
    icon: SparkleIcon,
  },
  {
    name: 'HIGHLIGHT_DETECTION',
    label: 'Détection des points clés',
    description: 'Risques juridiques, points importants et intox selon vos catégories.',
    icon: HighlighterIcon,
  },
  {
    name: 'REVIEW_DRAFTING',
    label: 'Rédaction de la revue',
    description: 'La synthèse finale est rédigée, prête à être partagée.',
    icon: PenLineIcon,
  },
]

interface StepDetail {
  done: number | null
  total: number | null
  unit: string
  failed: number
  retry: { attempt: number; next_in_seconds: number; reason: string } | null
}

// `result_summary` est un JSON libre côté API : on n'en extrait que ce qu'on sait afficher.
function stepDetail(step: PipelineStepRun | undefined): StepDetail {
  const summary = (step?.result_summary ?? {}) as Record<string, unknown>
  const num = (value: unknown) => (typeof value === 'number' ? value : null)
  const retry = summary.retry as StepDetail['retry'] | undefined
  return {
    done: num(summary.chunks_done),
    total: num(summary.chunks_total),
    unit: typeof summary.unit === 'string' ? summary.unit : 'éléments',
    failed: num(summary.documents_failed) ?? 0,
    retry: retry && typeof retry.reason === 'string' ? retry : null,
  }
}

export function stepStatus(steps: PipelineStepRun[], stepName: string) {
  return steps.find((s) => s.step_name === stepName)?.status ?? 'pending'
}

/** Frise verticale des 4 étapes du pipeline, avec la progression fine de l'étape en cours. */
export function ProgressStepper({ steps }: { steps: PipelineStepRun[] }) {
  return (
    <ol className="relative">
      {PIPELINE_STEPS.map((definition, index) => {
        const step = steps.find((s) => s.step_name === definition.name)
        const status = step?.status ?? 'pending'
        const detail = stepDetail(step)
        const isLast = index === PIPELINE_STEPS.length - 1
        const Icon = definition.icon
        return (
          <li key={definition.name} className="relative flex gap-4 pb-6 last:pb-0">
            {!isLast && (
              <span
                className={clsx(
                  'absolute top-11 bottom-1 left-[19px] w-0.5 rounded-full',
                  status === 'succeeded' ? 'bg-emerald-300' : 'bg-slate-200',
                )}
              />
            )}
            <div
              className={clsx(
                'relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ring-4 ring-white transition',
                status === 'succeeded' && 'bg-emerald-500 text-white',
                status === 'running' && 'bg-brand-600 text-white shadow-[var(--shadow-glow)]',
                status === 'failed' && 'bg-red-500 text-white',
                status === 'pending' && 'bg-slate-100 text-slate-400',
              )}
            >
              {status === 'succeeded' ? (
                <CheckIcon className="h-5 w-5" />
              ) : status === 'failed' ? (
                <AlertCircleIcon className="h-5 w-5" />
              ) : (
                <Icon className={clsx('h-5 w-5', status === 'running' && 'animate-pulse')} />
              )}
            </div>
            <div className="min-w-0 flex-1 pt-1">
              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                <p
                  className={clsx(
                    'text-sm font-semibold',
                    status === 'pending' ? 'text-slate-400' : 'text-slate-900',
                  )}
                >
                  {definition.label}
                </p>
                {status === 'running' && (
                  <span className="text-xs font-medium text-brand-700 tabular-nums">
                    {detail.total ? `${detail.done ?? 0} / ${detail.total} ${detail.unit}` : 'en cours…'}
                  </span>
                )}
                {status === 'succeeded' && <span className="text-xs font-medium text-emerald-600">Terminé</span>}
              </div>
              <p className={clsx('mt-0.5 text-xs', status === 'pending' ? 'text-slate-400' : 'text-slate-500')}>
                {definition.description}
              </p>
              {status === 'running' && (
                <ProgressBar percent={step?.progress_percent ?? 0} size="sm" className="mt-2.5 max-w-sm" />
              )}
              {status === 'running' && detail.retry && (
                <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800">
                  <ClockIcon className="mt-px h-3.5 w-3.5 shrink-0" />
                  <span>
                    {detail.retry.reason} Nouvelle tentative automatique dans {detail.retry.next_in_seconds} s (essai{' '}
                    {detail.retry.attempt}).
                  </span>
                </p>
              )}
              {detail.failed > 0 && status !== 'pending' && (
                <p className="mt-2 text-xs font-medium text-amber-700">
                  {detail.failed} fichier{detail.failed > 1 ? 's' : ''} illisible{detail.failed > 1 ? 's' : ''} ignoré
                  {detail.failed > 1 ? 's' : ''} — le reste de la revue n’est pas affecté.
                </p>
              )}
              {status === 'failed' && step?.error_message && (
                <p className="mt-2 rounded-lg bg-red-50 px-2.5 py-1.5 text-xs text-red-700">{step.error_message}</p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
