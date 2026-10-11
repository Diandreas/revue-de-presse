import type {
  PressReviewEntry,
  PressReviewRubrique,
  PressReviewSection,
  ReviewUpdateInput,
  StructuredReview,
} from '../../api/types'

/** Brouillon de la revue en mode « Modifier » : une copie locale, modifiée sans appel API
 * jusqu'à « Enregistrer ». Chaque notice porte un identifiant local (clé React stable quand
 * on la déplace). Les rubriques suivent l'ordre de la charte, vides comprises : une notice
 * peut être déplacée vers une rubrique qui n'en contenait aucune. */
export interface DraftEntry extends PressReviewEntry {
  id: string
}

export interface DraftSection {
  key: string
  entries: DraftEntry[]
}

export interface ReviewDraft {
  title: string
  dateLabel: string
  sections: DraftSection[]
}

export const UNIDENTIFIED_PREFIX = 'JOURNAL NON IDENTIFIÉ'

let nextId = 1
const localId = () => `notice-${nextId++}`

export function createDraft(review: StructuredReview, rubriques: PressReviewRubrique[], title: string): ReviewDraft {
  const byKey = new Map(review.sections.map((section) => [section.key, section]))
  // Rubrique présente dans la revue mais absente du catalogue (charte modifiée) : gardée en fin.
  const keys = [...rubriques.map((r) => r.key), ...review.sections.map((s) => s.key).filter((k) => !rubriques.some((r) => r.key === k))]
  return {
    title,
    dateLabel: review.date_label,
    sections: keys.map((key) => ({
      key,
      entries: (byKey.get(key)?.entries ?? []).map((entry) => ({ ...entry, documents: entry.documents ?? [], id: localId() })),
    })),
  }
}

function mapSection(draft: ReviewDraft, key: string, update: (entries: DraftEntry[]) => DraftEntry[]): ReviewDraft {
  return {
    ...draft,
    sections: draft.sections.map((section) => (section.key === key ? { ...section, entries: update(section.entries) } : section)),
  }
}

export function updateEntry(draft: ReviewDraft, key: string, id: string, patch: Partial<PressReviewEntry>): ReviewDraft {
  return mapSection(draft, key, (entries) => entries.map((entry) => (entry.id === id ? { ...entry, ...patch } : entry)))
}

export function removeEntry(draft: ReviewDraft, key: string, id: string): ReviewDraft {
  return mapSection(draft, key, (entries) => entries.filter((entry) => entry.id !== id))
}

/** Monte (-1) ou descend (+1) une notice dans sa rubrique. */
export function moveEntry(draft: ReviewDraft, key: string, id: string, delta: -1 | 1): ReviewDraft {
  return mapSection(draft, key, (entries) => {
    const from = entries.findIndex((entry) => entry.id === id)
    const to = from + delta
    if (from < 0 || to < 0 || to >= entries.length) return entries
    const next = [...entries]
    ;[next[from], next[to]] = [next[to], next[from]]
    return next
  })
}

/** Déplace une notice en fin de rubrique `toKey`. */
export function moveEntryToSection(draft: ReviewDraft, fromKey: string, id: string, toKey: string): ReviewDraft {
  if (fromKey === toKey) return draft
  const entry = draft.sections.find((s) => s.key === fromKey)?.entries.find((e) => e.id === id)
  if (!entry) return draft
  return mapSection(removeEntry(draft, fromKey, id), toKey, (entries) => [...entries, entry])
}

export function countEntries(draft: ReviewDraft) {
  return draft.sections.reduce((total, section) => total + section.entries.length, 0)
}

const clean = (text: string) => text.replace(/\s+/g, ' ').trim()

/** Problèmes bloquants, par notice (mêmes règles que le serveur, messages plus courts). */
export function draftProblems(draft: ReviewDraft): { byEntry: Map<string, string>; first: string | null } {
  const byEntry = new Map<string, string>()
  for (const section of draft.sections) {
    for (const entry of section.entries) {
      if (!clean(entry.source)) byEntry.set(entry.id, 'Indiquez le nom du journal.')
      else if (!clean(entry.headline) && !clean(entry.summary)) byEntry.set(entry.id, 'Indiquez le titre de la une ou un résumé.')
    }
  }
  let first: string | null = byEntry.size ? `${byEntry.size} notice${byEntry.size > 1 ? 's' : ''} à compléter avant d’enregistrer.` : null
  if (!clean(draft.title)) first = 'Le titre de la revue ne peut pas être vide.'
  else if (countEntries(draft) === 0) first = 'La revue doit contenir au moins une notice.'
  return { byEntry, first }
}

function sectionsPayload(draft: ReviewDraft) {
  return draft.sections
    .filter((section) => section.entries.length > 0)
    .map((section) => ({
      key: section.key,
      entries: section.entries.map(({ source, headline, summary, documents }) => ({ source, headline, summary, documents })),
    }))
}

/** Corps du PATCH : seulement ce qui a changé depuis l'ouverture de l'éditeur (renommer la
 * revue ne fige pas l'ordre des journaux). Objet vide = rien à enregistrer. */
export function draftChanges(draft: ReviewDraft, initial: ReviewDraft): ReviewUpdateInput {
  const changes: ReviewUpdateInput = {}
  if (draft.title.trim() !== initial.title.trim()) changes.title = draft.title.trim()
  if (draft.dateLabel.trim() !== initial.dateLabel.trim()) changes.date_label = draft.dateLabel.trim()
  const sections = sectionsPayload(draft)
  if (JSON.stringify(sections) !== JSON.stringify(sectionsPayload(initial))) changes.sections = sections
  return changes
}

/** Revue telle que le serveur la renverra (affichage optimiste pendant l'enregistrement). */
export function draftToStructured(draft: ReviewDraft, rubriques: PressReviewRubrique[], country: string): StructuredReview {
  const catalog = new Map(rubriques.map((r) => [r.key, r]))
  const sections: PressReviewSection[] = draft.sections
    .filter((section) => section.entries.length > 0)
    .map((section) => {
      const rubrique = catalog.get(section.key) ?? { key: section.key, title: section.key, color: '#1A237E', icon: '' }
      return {
        ...rubrique,
        entries: section.entries.map(({ source, headline, summary, documents }) => ({
          source: clean(source).toUpperCase(),
          headline: clean(headline).replace(/^[«»"“”'‘’\s]+|[«»"“”'‘’\s]+$/g, ''),
          summary: clean(summary),
          documents,
        })),
      }
    })
  return { country, date_label: clean(draft.dateLabel), sections }
}
