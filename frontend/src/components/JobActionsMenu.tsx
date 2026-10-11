import clsx from 'clsx'
import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { extractErrorMessage } from '../api/client'
import { useDeleteDenial, useDeleteJob, useRenameJob, type JobSummary } from '../features/jobs/useReviewEditing'
import { MoreHorizontalIcon, PenLineIcon, TrashIcon } from './icons'
import { Modal } from './Modal'
import { useToast } from './Toast'
import { Spinner } from './ui'

/** Menu « ⋯ » d'une revue : renommer, supprimer (avec confirmation). */
export function JobActionsMenu({
  job,
  onDeleted,
  className,
}: {
  job: JobSummary
  onDeleted?: () => void
  className?: string
}) {
  const toast = useToast()
  const menuId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [dialog, setDialog] = useState<'rename' | 'delete' | null>(null)
  const [title, setTitle] = useState(job.title)
  const renameMutation = useRenameJob()
  const deleteMutation = useDeleteJob()
  const deleteDenial = useDeleteDenial(job)
  const displayTitle = job.title || 'Revue sans titre'

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === 'Escape' : !rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const openDialog = (kind: 'rename' | 'delete') => {
    setOpen(false)
    if (kind === 'rename') setTitle(job.title)
    setDialog(kind)
  }

  const rename = async (event: FormEvent) => {
    event.preventDefault()
    const value = title.trim()
    if (!value) {
      toast.error('Le titre de la revue ne peut pas être vide.')
      return
    }
    try {
      await renameMutation.mutateAsync({ jobId: job.id, title: value })
      setDialog(null)
      toast.success('Revue renommée.')
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible de renommer la revue.'))
    }
  }

  const remove = async () => {
    try {
      await deleteMutation.mutateAsync(job.id)
      setDialog(null)
      toast.success('Revue supprimée.')
      onDeleted?.()
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible de supprimer la revue.'))
    }
  }

  return (
    <div ref={rootRef} className={clsx('relative', className)}>
      <button
        type="button"
        className="btn-icon"
        aria-label={`Actions pour « ${displayTitle} »`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
      >
        <MoreHorizontalIcon className="h-5 w-5" />
      </button>

      {open && (
        <div
          id={menuId}
          role="menu"
          className="absolute top-full right-0 z-30 mt-1 w-64 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-[var(--shadow-lifted)] animate-fade-in"
        >
          <button
            type="button"
            role="menuitem"
            className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
            onClick={() => openDialog('rename')}
          >
            <PenLineIcon className="h-4 w-4 text-slate-400" />
            Renommer
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={Boolean(deleteDenial)}
            title={deleteDenial ?? undefined}
            className="flex w-full items-start gap-2.5 px-3.5 py-2.5 text-left text-sm text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:bg-transparent"
            onClick={() => openDialog('delete')}
          >
            <TrashIcon className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Supprimer
              {deleteDenial && <span className="mt-0.5 block text-xs font-normal">{deleteDenial}</span>}
            </span>
          </button>
        </div>
      )}

      <Modal
        open={dialog === 'rename'}
        onClose={() => setDialog(null)}
        title="Renommer la revue"
        description="Le nouveau titre apparaît dans la liste des revues et sous le bandeau des exports."
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setDialog(null)}>
              Annuler
            </button>
            <button type="submit" form={`${menuId}-rename`} className="btn-primary" disabled={renameMutation.isPending}>
              {renameMutation.isPending && <Spinner />}
              Renommer
            </button>
          </>
        }
      >
        <form id={`${menuId}-rename`} onSubmit={(event) => void rename(event)}>
          <label htmlFor={`${menuId}-title`} className="label">
            Titre
          </label>
          <input
            id={`${menuId}-title`}
            className="input"
            value={title}
            maxLength={255}
            onChange={(event) => setTitle(event.target.value)}
          />
        </form>
      </Modal>

      <Modal
        open={dialog === 'delete'}
        onClose={() => setDialog(null)}
        title="Supprimer cette revue ?"
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setDialog(null)}>
              Annuler
            </button>
            <button type="button" className="btn-danger" disabled={deleteMutation.isPending} onClick={() => void remove()}>
              {deleteMutation.isPending ? <Spinner /> : <TrashIcon className="h-4 w-4" />}
              Supprimer définitivement
            </button>
          </>
        }
      >
        <div className="space-y-3 text-sm leading-relaxed text-slate-600">
          <p>
            <span className="font-semibold text-slate-900">« {displayTitle} »</span> sera effacée : documents source,
            revue, points clés et exports PDF / Word. Cette action est irréversible.
          </p>
          <p className="text-xs text-slate-500">La revue reste décomptée du quota de votre formule pour la période.</p>
        </div>
      </Modal>
    </div>
  )
}
