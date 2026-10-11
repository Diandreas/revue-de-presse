import axios from 'axios'
import clsx from 'clsx'
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import { Link } from 'react-router-dom'
import { extractErrorMessage } from '../api/client'
import type { SourceDocument } from '../api/types'
import { DocumentThumb } from '../components/DocumentGrid'
import {
  AlertCircleIcon,
  CameraIcon,
  CheckIcon,
  FileTextIcon,
  ImageIcon,
  LightbulbIcon,
  RefreshIcon,
  SparkleIcon,
  UploadCloudIcon,
  XIcon,
} from '../components/icons'
import { useToast } from '../components/Toast'
import { Alert, PageHeader, ProgressBar, Spinner } from '../components/ui'
import { blockingReason, usageStateOf } from '../features/billing/usage'
import { useSubscription } from '../features/billing/useBilling'
import { uploadDocument, useDeletePendingDocument, usePendingDocuments } from '../features/documents/useDocuments'
import { useCreateJob } from '../features/jobs/useJobs'
import { formatFileSize, plural } from '../lib/format'
import { canPreviewInBrowser, classifyLocalFile, prepareImageForUpload } from '../lib/imageCompression'

const ACCEPT = 'application/pdf,image/*,.pdf,.jpg,.jpeg,.png,.webp,.heic,.heif'
const MAX_FILE_BYTES = 30 * 1024 * 1024
const MAX_PARALLEL_UPLOADS = 3
const MAX_DOCUMENTS = 50

type ItemStatus = 'queued' | 'compressing' | 'uploading' | 'done' | 'error'

interface UploadItem {
  key: string
  name: string
  kind: 'pdf' | 'image'
  /** Taille réellement envoyée (après allègement éventuel de la photo). */
  size: number | null
  originalSize: number | null
  status: ItemStatus
  progress: number
  previewUrl: string | null
  /** Aperçu créé localement (URL.createObjectURL) : à libérer quand l'élément disparaît. */
  localPreview: boolean
  documentId?: string
  error?: string
}

function defaultTitle() {
  const date = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date())
  return `Revue de presse du ${date}`
}

function itemFromServer(doc: SourceDocument): UploadItem {
  return {
    key: `server-${doc.id}`,
    name: doc.original_filename,
    kind: doc.kind,
    size: null,
    originalSize: null,
    status: 'done',
    progress: 100,
    previewUrl: doc.kind === 'image' ? doc.file : null,
    localPreview: false,
    documentId: doc.id,
  }
}

let keySequence = 0
const nextKey = () => `local-${Date.now()}-${keySequence++}`

const TIPS = [
  'Photographiez la page à plat, bien éclairée, sans reflet.',
  'Une page (ou un article) par photo, texte bien net.',
  'Ajoutez les documents dans l’ordre où vous voulez les lire.',
]

export default function UploadPage() {
  const toast = useToast()
  const pendingQuery = usePendingDocuments()
  const deleteDocument = useDeletePendingDocument()
  const createJob = useCreateJob()
  const { data: subscription, isLoading: subscriptionLoading } = useSubscription()
  const blocking = blockingReason(usageStateOf(subscription, subscriptionLoading))

  const [items, setItems] = useState<UploadItem[]>([])
  const [title, setTitle] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [rejected, setRejected] = useState<string[]>([])
  const [submitError, setSubmitError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const filesRef = useRef(new Map<string, File>())
  const controllersRef = useRef(new Map<string, AbortController>())
  const queueRef = useRef<string[]>([])
  const activeUploadsRef = useRef(0)
  const dragDepthRef = useRef(0)
  const seededFromServerRef = useRef(false)
  const itemsRef = useRef<UploadItem[]>([])
  itemsRef.current = items

  const updateItem = useCallback((key: string, patch: Partial<UploadItem>) => {
    setItems((current) => current.map((item) => (item.key === key ? { ...item, ...patch } : item)))
  }, [])

  // Documents déjà téléversés lors d'une visite précédente (pas encore utilisés) : on les
  // reprend dans la liste, une seule fois, pour ne pas les perdre de vue.
  useEffect(() => {
    if (seededFromServerRef.current || !pendingQuery.data) return
    seededFromServerRef.current = true
    const fromServer = pendingQuery.data.slice().reverse().map(itemFromServer)
    if (fromServer.length) setItems((current) => [...fromServer, ...current])
  }, [pendingQuery.data])

  const runUpload = useCallback(
    async (key: string) => {
      const original = filesRef.current.get(key)
      if (!original) return
      const kind = classifyLocalFile(original)
      let prepared = original
      if (kind === 'image') {
        updateItem(key, { status: 'compressing' })
        prepared = await prepareImageForUpload(original)
      }
      if (!filesRef.current.has(key)) return // retiré pendant l'allègement

      const controller = new AbortController()
      controllersRef.current.set(key, controller)
      updateItem(key, { status: 'uploading', progress: 0, size: prepared.size })
      try {
        const document = await uploadDocument(prepared, {
          signal: controller.signal,
          onProgress: (percent) => updateItem(key, { progress: Math.min(percent, 99) }),
        })
        updateItem(key, { status: 'done', progress: 100, documentId: document.id })
      } catch (error) {
        if (axios.isCancel(error) || controller.signal.aborted) return
        updateItem(key, { status: 'error', error: extractErrorMessage(error, 'Échec de l’envoi.') })
      } finally {
        controllersRef.current.delete(key)
      }
    },
    [updateItem],
  )

  const pump = useCallback(() => {
    while (activeUploadsRef.current < MAX_PARALLEL_UPLOADS && queueRef.current.length > 0) {
      const key = queueRef.current.shift() as string
      activeUploadsRef.current += 1
      void runUpload(key).finally(() => {
        activeUploadsRef.current -= 1
        pump()
      })
    }
  }, [runUpload])

  const addFiles = useCallback(
    (fileList: FileList | File[]) => {
      const files = Array.from(fileList)
      if (files.length === 0) return
      const refused: string[] = []
      const accepted: UploadItem[] = []
      let room = MAX_DOCUMENTS - itemsRef.current.length

      for (const file of files) {
        const kind = classifyLocalFile(file)
        if (kind === 'unsupported') {
          refused.push(`${file.name} : format non pris en charge`)
          continue
        }
        if (file.size > MAX_FILE_BYTES) {
          refused.push(`${file.name} : plus de 30 Mo`)
          continue
        }
        if (room <= 0) {
          refused.push(`${file.name} : maximum ${MAX_DOCUMENTS} documents par revue`)
          continue
        }
        room -= 1
        const key = nextKey()
        filesRef.current.set(key, file)
        const preview = kind === 'image' && canPreviewInBrowser(file) ? URL.createObjectURL(file) : null
        accepted.push({
          key,
          name: file.name,
          kind,
          size: file.size,
          originalSize: file.size,
          status: 'queued',
          progress: 0,
          previewUrl: preview,
          localPreview: Boolean(preview),
        })
      }

      setRejected(refused)
      if (accepted.length) {
        setSubmitError(null)
        setItems((current) => [...current, ...accepted])
        queueRef.current.push(...accepted.map((item) => item.key))
        pump()
      }
    },
    [pump],
  )

  const removeItem = (item: UploadItem) => {
    controllersRef.current.get(item.key)?.abort()
    queueRef.current = queueRef.current.filter((key) => key !== item.key)
    filesRef.current.delete(item.key)
    if (item.localPreview && item.previewUrl) URL.revokeObjectURL(item.previewUrl)
    setItems((current) => current.filter((i) => i.key !== item.key))
    if (item.documentId) {
      deleteDocument.mutate(item.documentId, {
        onError: () => toast.error(`« ${item.name} » n’a pas pu être supprimé du serveur.`),
      })
    }
  }

  const retryItem = (item: UploadItem) => {
    updateItem(item.key, { status: 'queued', progress: 0, error: undefined })
    queueRef.current.push(item.key)
    pump()
  }

  // Coller une capture d'écran / une image copiée (Ctrl+V).
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const files = Array.from(event.clipboardData?.files ?? [])
      if (files.length) {
        event.preventDefault()
        addFiles(files)
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [addFiles])

  // Envois en cours : prévenir avant de quitter l'onglet.
  const busy = items.some((item) => item.status === 'queued' || item.status === 'compressing' || item.status === 'uploading')
  useEffect(() => {
    if (!busy) return
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [busy])

  // Libération des aperçus locaux et arrêt des envois en quittant la page.
  useEffect(() => {
    const controllers = controllersRef.current
    return () => {
      controllers.forEach((controller) => controller.abort())
      itemsRef.current.forEach((item) => {
        if (item.localPreview && item.previewUrl) URL.revokeObjectURL(item.previewUrl)
      })
    }
  }, [])

  const doneItems = items.filter((item) => item.status === 'done' && item.documentId)
  const errorCount = items.filter((item) => item.status === 'error').length
  const counts = useMemo(
    () => ({
      images: doneItems.filter((item) => item.kind === 'image').length,
      pdfs: doneItems.filter((item) => item.kind === 'pdf').length,
    }),
    [doneItems],
  )
  const uploadingCount = items.filter((item) => item.status !== 'done' && item.status !== 'error').length
  const canLaunch = doneItems.length > 0 && !busy && !blocking && !createJob.isPending

  const launch = async () => {
    setSubmitError(null)
    try {
      await createJob.mutateAsync({
        title: title.trim(),
        document_ids: doneItems.map((item) => item.documentId as string),
      })
      toast.success('Analyse lancée : elle se poursuit en arrière-plan.')
    } catch (error) {
      setSubmitError(extractErrorMessage(error, 'Impossible de lancer l’analyse.'))
    }
  }

  const onDragEnter = (event: DragEvent) => {
    event.preventDefault()
    dragDepthRef.current += 1
    setIsDragging(true)
  }
  const onDragLeave = (event: DragEvent) => {
    event.preventDefault()
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1)
    if (dragDepthRef.current === 0) setIsDragging(false)
  }
  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    dragDepthRef.current = 0
    setIsDragging(false)
    addFiles(event.dataTransfer.files)
  }

  const launchLabel = doneItems.length
    ? `Lancer l’analyse · ${plural(doneItems.length, 'document')}`
    : 'Lancer l’analyse'

  return (
    <div className="space-y-6 pb-28 lg:pb-0">
      <PageHeader
        back={{ to: '/dashboard', label: 'Revues de presse' }}
        eyebrow="Nouvelle revue"
        title="Déposez vos coupures de presse"
        subtitle="PDF ou photos de journaux, autant que nécessaire. Ils seront lus dans l’ordre ci-dessous, puis analysés en arrière-plan."
      />

      {blocking && (
        <Alert
          tone="warning"
          title="Impossible de lancer une nouvelle revue pour le moment"
          action={
            <Link to="/billing" className="btn-secondary btn-sm">
              Voir les formules
            </Link>
          }
        >
          {blocking}
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          {/* Zone de dépôt */}
          <div
            onDragEnter={onDragEnter}
            onDragOver={(e) => e.preventDefault()}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            className={clsx(
              'relative overflow-hidden rounded-3xl border-2 border-dashed p-8 text-center transition sm:p-10',
              isDragging
                ? 'scale-[1.01] border-brand-400 bg-brand-50/80 shadow-[var(--shadow-lifted)]'
                : 'border-slate-300/80 bg-white hover:border-brand-300 hover:bg-brand-50/30',
            )}
          >
            <div className="pointer-events-none absolute -top-16 -right-16 h-48 w-48 rounded-full bg-brand-200/30 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-amber-200/30 blur-3xl" />

            <div className="relative mx-auto flex w-fit items-center">
              <span className="flex h-12 w-12 -rotate-6 items-center justify-center rounded-2xl bg-white text-red-500 shadow-[var(--shadow-card)] ring-1 ring-slate-200">
                <FileTextIcon className="h-6 w-6" />
              </span>
              <span className="z-10 -mx-2 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-b from-brand-500 to-brand-700 text-white shadow-[var(--shadow-glow)]">
                <UploadCloudIcon className="h-7 w-7" />
              </span>
              <span className="flex h-12 w-12 rotate-6 items-center justify-center rounded-2xl bg-white text-amber-500 shadow-[var(--shadow-card)] ring-1 ring-slate-200">
                <ImageIcon className="h-6 w-6" />
              </span>
            </div>

            <p className="relative mt-5 font-display text-xl font-semibold text-slate-900">
              {isDragging ? (
                'Déposez vos fichiers ici'
              ) : (
                <>
                  {/* Pas de glisser-déposer sur téléphone : on y parle d'ajout. */}
                  <span className="hidden sm:inline">Glissez-déposez vos PDF et photos</span>
                  <span className="sm:hidden">Ajoutez vos PDF et photos</span>
                </>
              )}
            </p>
            <p className="relative mt-1.5 text-sm text-slate-500">
              <span className="hidden sm:inline">
                ou choisissez-les depuis votre appareil — plusieurs à la fois si vous le souhaitez.
              </span>
              <span className="sm:hidden">Plusieurs à la fois, depuis la galerie ou l’appareil photo.</span>
            </p>

            <div className="relative mt-6 flex flex-col items-center justify-center gap-2.5 sm:flex-row">
              <button type="button" className="btn-primary w-full sm:w-auto" onClick={() => fileInputRef.current?.click()}>
                <UploadCloudIcon className="h-4 w-4" />
                Choisir des fichiers
              </button>
              <button
                type="button"
                className="btn-secondary w-full sm:hidden"
                onClick={() => cameraInputRef.current?.click()}
              >
                <CameraIcon className="h-4 w-4" />
                Prendre une photo
              </button>
            </div>
            <p className="relative mt-5 text-xs text-slate-400">
              PDF, JPG, PNG, WebP, HEIC · 30 Mo max par fichier
              <span className="hidden sm:inline">
                {' '}
                · <span className="kbd">Ctrl</span> + <span className="kbd">V</span> pour coller une image
              </span>
            </p>

            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT}
              multiple
              className="hidden"
              onChange={(event) => {
                if (event.target.files) addFiles(event.target.files)
                event.target.value = ''
              }}
            />
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(event) => {
                if (event.target.files) addFiles(event.target.files)
                event.target.value = ''
              }}
            />
          </div>

          {rejected.length > 0 && (
            <Alert tone="warning" title="Certains fichiers n’ont pas été ajoutés">
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                {rejected.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            </Alert>
          )}

          {/* Documents de la revue */}
          {(items.length > 0 || pendingQuery.isLoading) && (
            <section className="card">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="section-title">Documents de la revue</h2>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {items.length ? `${plural(items.length, 'document')} · lus dans cet ordre` : 'Chargement…'}
                  </p>
                </div>
                {uploadingCount > 0 && (
                  <span className="chip bg-brand-50 text-brand-700 ring-1 ring-brand-200">
                    <Spinner className="h-3 w-3" />
                    {plural(uploadingCount, 'envoi')} en cours
                  </span>
                )}
              </div>

              <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
                {items.map((item, index) => (
                  <UploadTile
                    key={item.key}
                    item={item}
                    index={index}
                    onRemove={() => removeItem(item)}
                    onRetry={() => retryItem(item)}
                  />
                ))}
                <li>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex aspect-[4/5] w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-200 text-slate-400 transition hover:border-brand-300 hover:bg-brand-50/40 hover:text-brand-600"
                  >
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100">
                      <UploadCloudIcon className="h-5 w-5" />
                    </span>
                    <span className="text-xs font-semibold">Ajouter</span>
                  </button>
                </li>
              </ul>
            </section>
          )}
        </div>

        {/* Récapitulatif + lancement */}
        <aside className="space-y-5 lg:sticky lg:top-8 lg:self-start">
          <div className="card space-y-5">
            <div>
              <label className="label" htmlFor="review-title">
                Titre de la revue
              </label>
              <input
                id="review-title"
                className="input"
                placeholder={defaultTitle()}
                value={title}
                maxLength={255}
                onChange={(event) => setTitle(event.target.value)}
              />
              <p className="field-hint">Facultatif : la date du jour est utilisée par défaut.</p>
            </div>

            <dl className="grid grid-cols-2 gap-3">
              <div className="rounded-2xl bg-slate-50 px-4 py-3">
                <dt className="flex items-center gap-1.5 text-xs text-slate-500">
                  <ImageIcon className="h-3.5 w-3.5" /> Photos
                </dt>
                <dd className="mt-1 font-display text-2xl font-semibold text-slate-900 tabular-nums">{counts.images}</dd>
              </div>
              <div className="rounded-2xl bg-slate-50 px-4 py-3">
                <dt className="flex items-center gap-1.5 text-xs text-slate-500">
                  <FileTextIcon className="h-3.5 w-3.5" /> PDF
                </dt>
                <dd className="mt-1 font-display text-2xl font-semibold text-slate-900 tabular-nums">{counts.pdfs}</dd>
              </div>
            </dl>

            {errorCount > 0 && (
              <p className="text-xs font-medium text-amber-700">
                {plural(errorCount, 'fichier')} en erreur : réessayez ou retirez-{errorCount > 1 ? 'les' : 'le'}.
              </p>
            )}
            {submitError && <Alert tone="danger">{submitError}</Alert>}

            <button
              type="button"
              className="btn-primary btn-lg hidden w-full lg:inline-flex"
              disabled={!canLaunch}
              onClick={() => void launch()}
            >
              {createJob.isPending ? <Spinner /> : <SparkleIcon className="h-[18px] w-[18px]" />}
              {createJob.isPending ? 'Lancement…' : launchLabel}
            </button>
            <p className="flex items-start gap-2 text-xs leading-relaxed text-slate-500">
              <SparkleIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500" />
              L’analyse tourne sur nos serveurs : vous pourrez fermer la page, la revue apparaîtra dans votre tableau de
              bord dès qu’elle sera prête.
            </p>
          </div>

          <div className="surface-muted p-5">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <LightbulbIcon className="h-4 w-4 text-amber-500" />
              Pour une lecture parfaite
            </p>
            <ul className="mt-3 space-y-2">
              {TIPS.map((tip) => (
                <li key={tip} className="flex items-start gap-2 text-xs leading-relaxed text-slate-600">
                  <CheckIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                  {tip}
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>

      {/* Barre d'action fixe (mobile) */}
      <div className="safe-bottom fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/90 px-4 pt-3 backdrop-blur-md lg:hidden">
        <button
          type="button"
          className="btn-primary btn-lg w-full"
          disabled={!canLaunch}
          onClick={() => void launch()}
        >
          {createJob.isPending ? <Spinner /> : <SparkleIcon className="h-[18px] w-[18px]" />}
          {createJob.isPending ? 'Lancement…' : busy ? 'Envoi des fichiers…' : launchLabel}
        </button>
      </div>
    </div>
  )
}

function UploadTile({
  item,
  index,
  onRemove,
  onRetry,
}: {
  item: UploadItem
  index: number
  onRemove: () => void
  onRetry: () => void
}) {
  const inFlight = item.status === 'queued' || item.status === 'compressing' || item.status === 'uploading'
  const statusLabel =
    item.status === 'queued' ? 'En attente…' : item.status === 'compressing' ? 'Optimisation…' : `Envoi ${item.progress} %`
  const savedBytes = item.originalSize && item.size && item.size < item.originalSize * 0.9

  return (
    <li
      className={clsx(
        'group relative overflow-hidden rounded-2xl border bg-white shadow-[var(--shadow-soft)] animate-pop',
        item.status === 'error' ? 'border-red-200' : 'border-slate-200/80',
      )}
    >
      <div className="relative aspect-[4/5] overflow-hidden bg-slate-100">
        <DocumentThumb kind={item.kind} src={item.previewUrl} alt={item.name} />

        {inFlight && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-ink-950/45 px-4 backdrop-blur-[1px]">
            <Spinner className="h-6 w-6 text-white" />
            <div className="w-full">
              <ProgressBar percent={item.status === 'uploading' ? item.progress : 4} size="sm" tone="light" />
              <p className="mt-1.5 text-center text-[11px] font-semibold text-white tabular-nums">{statusLabel}</p>
            </div>
          </div>
        )}

        {item.status === 'error' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-red-950/55 px-3 text-center">
            <AlertCircleIcon className="h-6 w-6 text-white" />
            <p className="line-clamp-3 text-[11px] font-medium text-white">{item.error}</p>
            <button type="button" onClick={onRetry} className="btn-secondary btn-sm !h-7 !px-2.5 !text-xs">
              <RefreshIcon className="h-3.5 w-3.5" />
              Réessayer
            </button>
          </div>
        )}

        <span className="absolute top-2 left-2 flex h-6 min-w-6 items-center justify-center rounded-full bg-ink-950/75 px-1.5 text-[11px] font-semibold text-white backdrop-blur">
          {index + 1}
        </span>
        {item.status === 'done' && (
          <span className="absolute right-2 bottom-2 flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white shadow">
            <CheckIcon className="h-3.5 w-3.5" />
          </span>
        )}
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Retirer ${item.name}`}
          className="absolute top-2 right-2 flex h-7 w-7 items-center justify-center rounded-full bg-white/95 text-slate-600 shadow transition hover:bg-red-50 hover:text-red-600 sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100"
        >
          <XIcon className="h-4 w-4" />
        </button>
      </div>
      <div className="px-3 py-2.5">
        <p className="truncate text-xs font-medium text-slate-800" title={item.name}>
          {item.name}
        </p>
        <p className="mt-0.5 text-[11px] text-slate-400">
          {item.kind === 'image' ? 'Photo' : 'PDF'}
          {item.size ? ` · ${formatFileSize(item.size)}` : ''}
          {savedBytes && item.originalSize ? ` (au lieu de ${formatFileSize(item.originalSize)})` : ''}
        </p>
      </div>
    </li>
  )
}
