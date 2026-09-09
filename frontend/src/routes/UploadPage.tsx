import { useRef, useState } from 'react'
import { extractErrorMessage } from '../api/client'
import { usePendingDocuments, useUploadDocument } from '../features/documents/useDocuments'
import { useCreateJob } from '../features/jobs/useJobs'

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
      setSubmitError('Sélectionnez au moins un document PDF.')
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
      <h1 className="text-xl font-semibold text-slate-900">Nouvelle revue de presse</h1>
      <p className="mt-1 text-sm text-slate-500">
        Téléversez vos coupures de presse au format PDF, puis lancez la génération procédurale.
      </p>

      <div className="card mt-6">
        <label className="label">Titre de la revue (optionnel)</label>
        <input
          className="input"
          placeholder="Ex : Revue de presse — semaine du 11 août"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        <div className="mt-6 rounded-lg border-2 border-dashed border-slate-300 p-6 text-center">
          <p className="text-sm text-slate-600">Glissez vos fichiers PDF ici, ou</p>
          <button type="button" className="btn-secondary mt-3" onClick={() => fileInputRef.current?.click()}>
            Choisir des fichiers
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            multiple
            className="hidden"
            onChange={(e) => void handleFilesSelected(e.target.files)}
          />
          {uploadMutation.isPending && <p className="mt-2 text-xs text-slate-500">Téléversement en cours…</p>}
          {uploadError && <p className="mt-2 text-xs text-red-600">{uploadError}</p>}
        </div>

        <div className="mt-6">
          <h2 className="text-sm font-medium text-slate-700">Documents disponibles</h2>
          {isLoading && <p className="mt-2 text-sm text-slate-500">Chargement…</p>}
          {documents && documents.length === 0 && (
            <p className="mt-2 text-sm text-slate-500">Aucun document en attente — téléversez un PDF ci-dessus.</p>
          )}
          <ul className="mt-2 divide-y divide-slate-100">
            {documents?.map((doc) => (
              <li key={doc.id} className="flex items-center gap-3 py-2">
                <input
                  type="checkbox"
                  checked={selectedIds.has(doc.id)}
                  onChange={() => toggleSelected(doc.id)}
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="truncate text-sm text-slate-700">{doc.original_filename}</span>
              </li>
            ))}
          </ul>
        </div>

        {submitError && <p className="mt-4 text-sm text-red-600">{submitError}</p>}
        <button
          type="button"
          className="btn-primary mt-6 w-full"
          disabled={createJobMutation.isPending}
          onClick={() => void handleSubmit()}
        >
          {createJobMutation.isPending ? 'Lancement…' : 'Générer la revue de presse'}
        </button>
      </div>
    </div>
  )
}
