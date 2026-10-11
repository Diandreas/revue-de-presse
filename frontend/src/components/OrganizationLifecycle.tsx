import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { useCloseOrganization, useExportOrganization, useLeaveOrganization } from '../features/account/useAccount'
import { AlertTriangleIcon, DownloadIcon, LogOutIcon, TrashIcon } from './icons'
import { Modal } from './Modal'
import { useToast } from './Toast'
import { Alert, Spinner } from './ui'

type Dialog = 'leave' | 'close' | null

function Row({ title, description, action }: { title: string; description: string; action: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-slate-900">{title}</p>
        <p className="mt-0.5 text-[13px] leading-relaxed text-slate-500">{description}</p>
      </div>
      <div className="shrink-0">{action}</div>
    </div>
  )
}

/** Vos données et votre accès : export (propriétaires), quitter l'organisation, fermeture
 * de l'organisation (propriétaires). */
export function OrganizationLifecycle() {
  const toast = useToast()
  const navigate = useNavigate()
  const { organization, refreshOrganization } = useAuth()
  const isOwner = organization?.my_role === 'owner'
  const exportData = useExportOrganization()
  const leave = useLeaveOrganization()
  const close = useCloseOrganization()
  const [dialog, setDialog] = useState<Dialog>(null)
  const [confirmName, setConfirmName] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const openDialog = (value: Dialog) => {
    setError(null)
    setConfirmName('')
    setReason('')
    setDialog(value)
  }

  const handleExport = async () => {
    try {
      await exportData.mutateAsync()
      toast.success('Export téléchargé.')
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Impossible d’exporter les données pour le moment.'))
    }
  }

  /** Après un départ ou une fermeture : bascule sur une autre organisation, ou écran dédié. */
  const afterLeaving = async (message: string) => {
    setDialog(null)
    toast.success(message)
    await refreshOrganization()
    navigate('/dashboard', { replace: true })
  }

  const handleLeave = async () => {
    setError(null)
    try {
      await leave.mutateAsync()
      await afterLeaving(`Vous avez quitté ${organization?.name ?? 'l’organisation'}.`)
    } catch (err) {
      setError(extractErrorMessage(err, 'Impossible de quitter l’organisation.'))
    }
  }

  const handleClose = async () => {
    setError(null)
    try {
      const detail = await close.mutateAsync({ confirm_name: confirmName, reason })
      await afterLeaving(detail)
    } catch (err) {
      setError(extractErrorMessage(err, 'Impossible de fermer l’organisation.'))
    }
  }

  return (
    <section className="card">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
          <AlertTriangleIcon className="h-5 w-5" />
        </span>
        <div>
          <h2 className="section-title">Vos données et votre accès</h2>
          <p className="text-xs text-slate-500">Export, départ de l’organisation et fermeture.</p>
        </div>
      </div>

      <div className="mt-4 divide-y divide-slate-100 border-t border-slate-100">
        {isOwner && (
          <Row
            title="Exporter les données"
            description="Revues, points clés, membres et factures (sans montants) dans un fichier JSON."
            action={
              <button
                type="button"
                className="btn-secondary btn-sm"
                disabled={exportData.isPending}
                onClick={() => void handleExport()}
              >
                {exportData.isPending ? <Spinner /> : <DownloadIcon className="h-4 w-4" />}
                Exporter
              </button>
            }
          />
        )}
        <Row
          title="Quitter l’organisation"
          description="Vous n’aurez plus accès à ses revues. Le dernier propriétaire doit d’abord transférer la propriété."
          action={
            <button type="button" className="btn-secondary btn-sm" onClick={() => openDialog('leave')}>
              <LogOutIcon className="h-4 w-4" />
              Quitter
            </button>
          }
        />
        {isOwner && (
          <Row
            title="Fermer l’organisation"
            description="L’accès est coupé pour toute l’équipe ; les données sont ensuite supprimées par notre équipe."
            action={
              <button type="button" className="btn-danger btn-sm" onClick={() => openDialog('close')}>
                <TrashIcon className="h-4 w-4" />
                Fermer
              </button>
            }
          />
        )}
      </div>

      <Modal
        open={dialog === 'leave'}
        onClose={() => setDialog(null)}
        title="Quitter l’organisation ?"
        description={organization?.name}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setDialog(null)}>
              Annuler
            </button>
            <button type="button" className="btn-danger" disabled={leave.isPending} onClick={() => void handleLeave()}>
              {leave.isPending ? <Spinner /> : <LogOutIcon className="h-4 w-4" />}
              Quitter
            </button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-slate-600">
          Vous n’aurez plus accès aux revues, documents et catégories de cette organisation. Un administrateur pourra
          vous inviter à nouveau.
        </p>
        {error && (
          <Alert tone="danger" className="mt-4">
            {error}
          </Alert>
        )}
      </Modal>

      <Modal
        open={dialog === 'close'}
        onClose={() => setDialog(null)}
        title="Fermer l’organisation ?"
        description="Cette action coupe l’accès de toute l’équipe."
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setDialog(null)}>
              Annuler
            </button>
            <button
              type="button"
              className="btn-danger"
              disabled={close.isPending || confirmName.trim() === ''}
              onClick={() => void handleClose()}
            >
              {close.isPending ? <Spinner /> : <TrashIcon className="h-4 w-4" />}
              Fermer définitivement
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <Alert tone="warning">
            Plus personne ne pourra se connecter à cet espace. Pensez à exporter vos données avant. Les revues et fichiers
            seront ensuite supprimés par l’équipe Revue de Presse.
          </Alert>
          <div>
            <label className="label" htmlFor="close-confirm-name">
              Tapez <strong>{organization?.name}</strong> pour confirmer
            </label>
            <input
              id="close-confirm-name"
              className="input"
              autoComplete="off"
              value={confirmName}
              onChange={(e) => setConfirmName(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="close-reason">
              Raison (facultatif)
            </label>
            <textarea
              id="close-reason"
              className="input min-h-[80px]"
              value={reason}
              maxLength={2000}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          {error && <Alert tone="danger">{error}</Alert>}
        </div>
      </Modal>
    </section>
  )
}
