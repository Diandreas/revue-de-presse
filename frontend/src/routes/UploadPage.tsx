import { useRef, useState } from 'react'
import { extractErrorMessage } from '../api/client'
import type { SourceDocumentKind } from '../api/types'
import { FileTextIcon, ImageIcon, SparkleIcon, UploadCloudIcon } from '../components/icons'
import { usePendingDocuments, useUploadDocument } from '../features/documents/useDocuments'
import { useCreateJob } from '../features/jobs/useJobs'

const ACCEPT = 'application/pdf,image/*,.pdf,.jpg,.jpeg,.png,.webp,.tif,.tiff,.heic,.heif'

function KindBadge({ kind }: { kind: SourceDocumentKind }) {
  const Icon = kind === 'image' ? ImageIcon : FileTextIcon
  return (
    <span className="chip shrink-0 bg-slate-100 text-slate-600">
      <Icon className="h-3 w-3" />
      {kind === 'image' ? 'Photo' : 'PDF'}
    </span>
  )
}

export default function UploadPage() {
  const { data: documents, isLoading } = usePendingDocuments()
  const uploadMutation = useUploadDocument()
  const createJobMutation = useCreateJob()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [title, setTitle] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const handleFilesSelected = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploadError(null)
    for (const file of Array.from(files)) {
      try {
        const document = await uploadMutation.mutateAsync(file)
        setSelectedIds((prev) => new Set(prev).add(document.id))
      } catch (error) {
        setUploadError(extractErrorMessage(error, `Échec du téléversement de ${file.name}.`))
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const toggleSelected = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleSubmit = async () => {
    setSubmitError(null)
    if (selectedIds.size === 0) {
      setSubmitError('Sélectionnez au moins un document (PDF ou photo).')
      return
    }
    try {
      await createJobMutation.mutateAsync({ title, document_ids: Array.from(selectedIds) })
    } catch (error) {
      setSubmitError(extractErrorMessage(error, 'Impossible de lancer la génération.'))
    }
  }

  return (
    <div>
      <h1 className="page-title">Nouvelle revue de presse</h1>
      <p className="page-subtitle">
        Téléversez vos coupures de presse — fichiers PDF ou photos (JPG, PNG, HEIC…), en une ou plusieurs fois —
        puis lancez la génération procédurale.
      </p>

      <div className="card mt-6">
        <label className="label">Titre de la revue (optionnel)</label>
        <input
          className="input"
          placeholder="Ex : Revue de presse — semaine du 11 août"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        <div
          className="mt-6 rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/60 p-8 text-center transition-colors hover:border-brand-300 hover:bg-brand-50/30"
          onClick={() => fileInputRef.current?.click()}
          role="button"
        >
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-white text-brand-600 shadow-[var(--shadow-soft)]">
            <UploadCloudIcon className="h-5 w-5" />
          </div>
          <p className="mt-3 text-sm font-medium text-slate-700">Glissez vos PDF ou photos ici</p>
          <p className="mt-0.5 text-xs text-slate-400">ou cliquez pour parcourir vos fichiers</p>
          <button
            type="button"
            className="btn-secondary mt-4"
            onClick={(e) => {
              e.stopPropagation()
              fileInputRef.current?.click()
            }}
          >
            Choisir des fichiers
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT}
            multiple
            className="hidden"
            onChange={(e) => void handleFilesSelected(e.target.files)}
          />
          {uploadMutation.isPending && <p className="mt-3 text-xs text-brand-600">Téléversement en cours…</p>}
          {uploadError && <p className="mt-3 text-xs text-red-600">{uploadError}</p>}
        </div>

        <div className="mt-6">
          <h2 className="section-title">Documents disponibles</h2>
          {isLoading && <p className="mt-2 text-sm text-slate-500">Chargement…</p>}
          {documents && documents.length === 0 && (
            <p className="mt-2 text-sm text-slate-500">
              Aucun document en attente — téléversez un PDF ou une photo ci-dessus.
            </p>
          )}
          <ul className="mt-2 divide-y divide-slate-100">
            {documents?.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-slate-50"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(doc.id)}
                  onChange={() => toggleSelected(doc.id)}
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="min-w-0 flex-1 truncate text-sm text-slate-700">{doc.original_filename}</span>
                <KindBadge kind={doc.kind} />
              </li>
            ))}
          </ul>
        </div>

        {submitError && (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{submitError}</p>
        )}
        <button
          type="button"
          className="btn-primary mt-6 w-full"
          disabled={createJobMutation.isPending}
          onClick={() => void handleSubmit()}
        >
          <SparkleIcon className="h-4 w-4" />
          {createJobMutation.isPending ? 'Lancement…' : 'Générer la revue de presse'}
        </button>
      </div>
    </div>
  )
}
