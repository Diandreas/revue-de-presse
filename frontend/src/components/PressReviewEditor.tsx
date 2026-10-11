import clsx from 'clsx'
import { useLayoutEffect, useRef, useState, type TextareaHTMLAttributes } from 'react'
import type { PressReviewRubrique } from '../api/types'
import {
  moveEntry,
  moveEntryToSection,
  removeEntry,
  UNIDENTIFIED_PREFIX,
  updateEntry,
  type DraftEntry,
  type ReviewDraft,
} from '../features/jobs/reviewDraft'
import { AlertTriangleIcon, ArrowDownIcon, ArrowUpIcon, TrashIcon } from './icons'

/** Zone de texte qui grandit avec son contenu (pas d'ascenseur dans un résumé). */
function AutoTextarea({ value, className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & { value: string }) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${element.scrollHeight + 2}px`
  }, [value])
  return <textarea ref={ref} rows={3} value={value} className={clsx('resize-none', className)} {...props} />
}

interface EntryEditorProps {
  entry: DraftEntry
  sectionKey: string
  index: number
  count: number
  rubriques: PressReviewRubrique[]
  problem?: string
  onDraft: (update: (draft: ReviewDraft) => ReviewDraft) => void
}

function EntryEditor({ entry, sectionKey, index, count, rubriques, problem, onDraft }: EntryEditorProps) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const label = entry.source.trim() || `notice ${index + 1}`
  const unidentified = entry.source.trim().toUpperCase().startsWith(UNIDENTIFIED_PREFIX)
  const set = (patch: Partial<DraftEntry>) => onDraft((draft) => updateEntry(draft, sectionKey, entry.id, patch))

  return (
    <article
      className={clsx(
        'rounded-xl border bg-white/80 p-3 shadow-sm sm:p-4',
        problem ? 'border-red-300' : unidentified ? 'border-amber-300' : 'border-slate-200',
      )}
    >
      <div className="flex items-center gap-2">
        <span aria-hidden="true" className="font-bold text-[#8B0000]">
          ▶
        </span>
        <input
          className="input !h-9 min-w-0 flex-1 !px-2.5 font-bold tracking-wide text-[#8B0000] uppercase"
          value={entry.source}
          maxLength={150}
          placeholder="NOM DU JOURNAL"
          aria-label={`Nom du journal (${label})`}
          onChange={(event) => set({ source: event.target.value })}
        />
        <div className="flex shrink-0 items-center">
          <button
            type="button"
            className="btn-icon !h-8 !w-8"
            disabled={index === 0}
            aria-label={`Monter ${label}`}
            title="Monter"
            onClick={() => onDraft((draft) => moveEntry(draft, sectionKey, entry.id, -1))}
          >
            <ArrowUpIcon className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="btn-icon !h-8 !w-8"
            disabled={index === count - 1}
            aria-label={`Descendre ${label}`}
            title="Descendre"
            onClick={() => onDraft((draft) => moveEntry(draft, sectionKey, entry.id, 1))}
          >
            <ArrowDownIcon className="h-4 w-4" />
          </button>
          {confirmDelete ? (
            <button
              type="button"
              className="ml-1 inline-flex h-8 items-center rounded-lg bg-red-600 px-2.5 text-xs font-semibold text-white hover:bg-red-700"
              onClick={() => onDraft((draft) => removeEntry(draft, sectionKey, entry.id))}
              onBlur={() => setConfirmDelete(false)}
              autoFocus
            >
              Confirmer
            </button>
          ) : (
            <button
              type="button"
              className="btn-icon !h-8 !w-8 hover:!bg-red-50 hover:!text-red-600"
              aria-label={`Supprimer ${label}`}
              title="Supprimer la notice"
              onClick={() => setConfirmDelete(true)}
            >
              <TrashIcon className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {unidentified && (
        <p className="mt-1.5 flex items-center gap-1.5 text-xs font-medium text-amber-700">
          <AlertTriangleIcon className="h-3.5 w-3.5" />
          Journal non reconnu par l’IA : indiquez son nom.
        </p>
      )}

      <input
        className="input mt-2.5 !h-9 !px-2.5 font-medium"
        value={entry.headline}
        maxLength={300}
        placeholder="Titre de la une (sans guillemets)"
        aria-label={`Titre de la une (${label})`}
        onChange={(event) => set({ headline: event.target.value })}
      />
      <AutoTextarea
        className="input mt-2 !px-2.5 !py-2 text-[15px] leading-relaxed"
        value={entry.summary}
        maxLength={5000}
        placeholder="Résumé de la une"
        aria-label={`Résumé (${label})`}
        onChange={(event) => set({ summary: event.target.value })}
      />

      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <label htmlFor={`${entry.id}-rubrique`}>Rubrique</label>
        <select
          id={`${entry.id}-rubrique`}
          className="max-w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
          value={sectionKey}
          onChange={(event) => onDraft((draft) => moveEntryToSection(draft, sectionKey, entry.id, event.target.value))}
        >
          {rubriques.map((rubrique) => (
            <option key={rubrique.key} value={rubrique.key}>
              {rubrique.icon} {rubrique.title}
            </option>
          ))}
        </select>
      </div>

      {problem && <p className="field-error">{problem}</p>}
    </article>
  )
}

interface PressReviewEditorProps {
  draft: ReviewDraft
  onChange: (update: (draft: ReviewDraft) => ReviewDraft) => void
  rubriques: PressReviewRubrique[]
  country: string
  /** Notices à compléter (affichées après une tentative d'enregistrement). */
  problems: Map<string, string>
}

/** Mode « Modifier » de la revue : même mise en page que la feuille de revue, chaque
 * notice devenant un petit formulaire (journal, titre de la une, résumé, rubrique). */
export function PressReviewEditor({ draft, onChange, rubriques, country, problems }: PressReviewEditorProps) {
  const catalog = new Map(rubriques.map((r) => [r.key, r]))
  const options = draft.sections.map(
    (section) => catalog.get(section.key) ?? { key: section.key, title: section.key, color: '#1A237E', icon: '' },
  )

  return (
    <div>
      <div className="mb-5">
        <label htmlFor="review-title" className="label">
          Titre de la revue
        </label>
        <input
          id="review-title"
          className={clsx('input', !draft.title.trim() && 'input-error')}
          value={draft.title}
          maxLength={255}
          onChange={(event) => onChange((current) => ({ ...current, title: event.target.value }))}
        />
        <p className="field-hint">Affiché dans la liste des revues et sous le bandeau des exports PDF et Word.</p>
      </div>

      <header className="rounded-2xl bg-[#1A237E] px-4 py-5 text-center text-white shadow-sm sm:py-6">
        <p className="text-2xl font-bold tracking-[0.06em] sm:text-3xl">REVUE DE PRESSE</p>
        <div className="mx-auto mt-2 flex max-w-md items-center justify-center gap-2 text-sm text-[#AAAAFF]">
          {country && <span className="shrink-0 tracking-wide">{country} —</span>}
          <input
            className="h-8 min-w-0 flex-1 rounded-lg border border-white/25 bg-white/10 px-2.5 text-center text-white placeholder:text-white/50 focus:border-white/60 focus:outline-none"
            value={draft.dateLabel}
            maxLength={100}
            placeholder="Date de la revue"
            aria-label="Date affichée dans le bandeau"
            onChange={(event) => onChange((current) => ({ ...current, dateLabel: event.target.value }))}
          />
        </div>
      </header>

      {draft.sections.map((section) => {
        if (section.entries.length === 0) return null
        const rubrique = catalog.get(section.key)
        return (
          <section key={section.key} className="mt-8">
            <h2
              className="flex items-center gap-2.5 rounded-lg px-4 py-2.5 text-[13px] font-bold tracking-wide text-white sm:text-sm"
              style={{ backgroundColor: rubrique?.color ?? '#1A237E' }}
            >
              <span aria-hidden="true">{rubrique?.icon}</span>
              {rubrique?.title ?? section.key}
            </h2>
            <div className="mt-3 space-y-3">
              {section.entries.map((entry, index) => (
                <EntryEditor
                  key={entry.id}
                  entry={entry}
                  sectionKey={section.key}
                  index={index}
                  count={section.entries.length}
                  rubriques={options}
                  problem={problems.get(entry.id)}
                  onDraft={onChange}
                />
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}
