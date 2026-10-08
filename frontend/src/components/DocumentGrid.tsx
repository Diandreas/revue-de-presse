import clsx from 'clsx'
import { useState } from 'react'
import type { SourceDocument } from '../api/types'
import { AlertTriangleIcon, CheckIcon, FileTextIcon, ImageIcon } from './icons'
import { Spinner } from './ui'

/** Vignette d'un document : la photo elle-même, ou une page stylisée pour un PDF. */
export function DocumentThumb({
  kind,
  src,
  alt,
  className,
}: {
  kind: 'pdf' | 'image'
  src?: string | null
  alt: string
  className?: string
}) {
  const [failed, setFailed] = useState(false)
  if (kind === 'image' && src && !failed) {
    return (
      <img
        src={src}
        alt={alt}
        loading="lazy"
        onError={() => setFailed(true)}
        className={clsx('h-full w-full object-cover', className)}
      />
    )
  }
  const Icon = kind === 'image' ? ImageIcon : FileTextIcon
  return (
    <div
      className={clsx(
        'flex h-full w-full flex-col items-center justify-center gap-2 bg-gradient-to-b from-slate-50 to-slate-100 text-slate-400',
        className,
      )}
    >
      {kind === 'pdf' ? (
        <div className="relative flex h-[58%] w-[52%] flex-col gap-1.5 rounded-md bg-white p-2.5 shadow-sm ring-1 ring-slate-200">
          <span className="h-1.5 w-3/4 rounded bg-slate-300" />
          <span className="h-1 w-full rounded bg-slate-200" />
          <span className="h-1 w-full rounded bg-amber-200" />
          <span className="h-1 w-5/6 rounded bg-slate-200" />
          <span className="h-1 w-2/3 rounded bg-slate-200" />
          <span className="absolute -right-2 -bottom-2 rounded bg-red-500 px-1.5 py-0.5 text-[9px] font-bold text-white">
            PDF
          </span>
        </div>
      ) : (
        <Icon className="h-8 w-8" />
      )}
    </div>
  )
}

function DocumentStatus({ doc, processing }: { doc: SourceDocument; processing: boolean }) {
  if (doc.extraction_status === 'done') {
    const pages = doc.page_count && doc.kind === 'pdf' ? ` · ${doc.page_count} p.` : ''
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700">
        <CheckIcon className="h-3.5 w-3.5" />
        Lu{pages}
      </span>
    )
  }
  if (doc.extraction_status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-700" title={doc.extraction_error}>
        <AlertTriangleIcon className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{doc.extraction_error || 'Illisible — ignoré'}</span>
      </span>
    )
  }
  return processing ? (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-brand-700">
      <Spinner className="h-3 w-3" />
      Lecture…
    </span>
  ) : (
    <span className="text-[11px] text-slate-400">En attente</span>
  )
}

/** Documents d'une revue, dans leur ordre de lecture (= ordre de téléversement). */
export function DocumentGrid({ documents, processing = false }: { documents: SourceDocument[]; processing?: boolean }) {
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {documents.map((doc, index) => (
        <li
          key={doc.id}
          className={clsx(
            'group overflow-hidden rounded-2xl border bg-white shadow-[var(--shadow-soft)] transition',
            doc.extraction_status === 'failed' ? 'border-amber-200' : 'border-slate-200/80',
          )}
        >
          <a
            href={doc.file}
            target="_blank"
            rel="noopener noreferrer"
            className="relative block aspect-[4/5] overflow-hidden bg-slate-100"
            title={`Ouvrir ${doc.original_filename}`}
          >
            <DocumentThumb
              kind={doc.kind}
              src={doc.file}
              alt={doc.original_filename}
              className="transition duration-300 group-hover:scale-[1.03]"
            />
            <span className="absolute top-2 left-2 flex h-6 min-w-6 items-center justify-center rounded-full bg-ink-950/75 px-1.5 text-[11px] font-semibold text-white backdrop-blur">
              {index + 1}
            </span>
          </a>
          <div className="space-y-1 px-3 py-2.5">
            <p className="truncate text-xs font-medium text-slate-800" title={doc.original_filename}>
              {doc.original_filename}
            </p>
            <DocumentStatus doc={doc} processing={processing} />
          </div>
        </li>
      ))}
    </ul>
  )
}
