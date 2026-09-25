import type { SourceDocument } from '../api/types'

function status(doc: SourceDocument): { text: string; className: string } {
  if (doc.extraction_status === 'done') {
    const pages = doc.page_count ? ` · ${doc.page_count} page${doc.page_count > 1 ? 's' : ''}` : ''
    return { text: `Lu${pages}`, className: 'text-green-700' }
  }
  if (doc.extraction_status === 'failed') {
    return { text: doc.extraction_error || 'Illisible — ignoré', className: 'text-amber-700' }
  }
  return { text: 'En attente', className: 'text-slate-500' }
}

/** Documents du job dans leur ordre de lecture (= ordre d'upload), avec l'état de chaque lecture. */
export function DocumentsList({ documents }: { documents: SourceDocument[] }) {
  return (
    <ul className="divide-y divide-slate-100">
      {documents.map((doc, index) => {
        const s = status(doc)
        return (
          <li key={doc.id} className="flex items-center gap-3 py-2">
            <span className="w-5 shrink-0 text-xs text-slate-400">{index + 1}.</span>
            <span className="min-w-0 flex-1 truncate text-sm text-slate-700">{doc.original_filename}</span>
            <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
              {doc.kind === 'image' ? 'Photo' : 'PDF'}
            </span>
            <span className={`shrink-0 text-xs ${s.className}`}>{s.text}</span>
          </li>
        )
      })}
    </ul>
  )
}
