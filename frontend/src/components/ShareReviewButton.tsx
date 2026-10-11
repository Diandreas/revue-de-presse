import { useRef, useState } from 'react'
import { apiClient, extractErrorMessage } from '../api/client'
import {
  canShareFiles,
  canShareText,
  isShareActivationLost,
  isShareCancelled,
  whatsappShareUrl,
  WHATSAPP_TEXT_SOFT_LIMIT,
} from '../lib/share'
import { DownloadIcon, ShareIcon, WhatsAppIcon } from './icons'
import { Modal } from './Modal'
import { useToast } from './Toast'
import { CopyButton, Spinner } from './ui'

interface ShareReviewButtonProps {
  title: string
  /** Texte brut de la revue (copier / WhatsApp). */
  text: string
  /** Nom du fichier PDF partagé (« revue-du-jeudi.pdf »). */
  fileName: string
  /** Génère (ou retrouve) l'export PDF et renvoie son URL. */
  getPdfUrl: () => Promise<string>
  /** Change à chaque correction de la revue : le PDF préparé n'est alors plus à jour. */
  version: string
  onDownloadPdf: () => void
}

/** « Partager » : sur mobile, la feuille de partage du téléphone avec le PDF en pièce jointe
 * (WhatsApp, e-mail…). Ailleurs, une fenêtre avec le texte pour WhatsApp, la copie du
 * texte et le téléchargement du PDF. */
export function ShareReviewButton({ title, text, fileName, getPdfUrl, version, onDownloadPdf }: ShareReviewButtonProps) {
  const toast = useToast()
  const [preparing, setPreparing] = useState(false)
  const [fallbackOpen, setFallbackOpen] = useState(false)
  const prepared = useRef<{ version: string; file: File } | null>(null)

  const loadPdf = async () => {
    if (prepared.current?.version === version) return prepared.current.file
    const url = await getPdfUrl()
    // Via le client API : même session (jeton) si les fichiers deviennent privés.
    const res = await apiClient.get<Blob>(url, { responseType: 'blob' })
    const file = new File([res.data], fileName, { type: 'application/pdf' })
    prepared.current = { version, file }
    return file
  }

  const share = async () => {
    if (!canShareFiles()) {
      setFallbackOpen(true)
      return
    }
    // PDF déjà prêt : le partage part dans le même geste. Sinon, le navigateur peut refuser
    // un partage lancé après le téléchargement (geste « expiré ») : on redemande un toucher.
    const wasReady = prepared.current?.version === version
    setPreparing(true)
    try {
      const file = await loadPdf()
      await navigator.share({ files: [file], title, text: title })
    } catch (error) {
      if (isShareCancelled(error)) return
      if (isShareActivationLost(error) && !wasReady && prepared.current) {
        toast.info('Le PDF est prêt : touchez à nouveau « Partager » pour l’envoyer.')
        return
      }
      if (!(error instanceof DOMException)) {
        toast.error(extractErrorMessage(error, 'Impossible de préparer le PDF. Partagez le texte à la place.'))
      }
      setFallbackOpen(true)
    } finally {
      setPreparing(false)
    }
  }

  const shareText = async () => {
    try {
      await navigator.share({ title, text })
      setFallbackOpen(false)
    } catch (error) {
      if (!isShareCancelled(error)) toast.error('Le partage n’a pas abouti. Copiez le texte à la place.')
    }
  }

  return (
    <>
      <button type="button" className="btn-secondary" disabled={preparing} onClick={() => void share()}>
        {preparing ? <Spinner /> : <ShareIcon className="h-4 w-4" />}
        {preparing ? 'Préparation…' : 'Partager'}
      </button>

      <Modal
        open={fallbackOpen}
        onClose={() => setFallbackOpen(false)}
        title="Partager la revue"
        description="Envoyez-la à votre direction ou à vos groupes WhatsApp."
      >
        <div className="space-y-3">
          <a
            href={whatsappShareUrl(text)}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary w-full justify-start"
            onClick={() => setFallbackOpen(false)}
          >
            <WhatsAppIcon className="h-[18px] w-[18px] text-emerald-500" />
            Envoyer le texte sur WhatsApp
          </a>
          {text.length > WHATSAPP_TEXT_SOFT_LIMIT && (
            <p className="field-hint !mt-1">
              Revue longue : WhatsApp peut couper le texte. Préférez le PDF, à joindre depuis WhatsApp.
            </p>
          )}
          {canShareText() && (
            <button type="button" className="btn-secondary w-full justify-start" onClick={() => void shareText()}>
              <ShareIcon className="h-4 w-4" />
              Partager le texte avec une autre application
            </button>
          )}
          <CopyButton text={text} label="Copier le texte" className="!h-10 w-full !justify-start !px-4" />
          <button
            type="button"
            className="btn-secondary w-full justify-start"
            onClick={() => {
              setFallbackOpen(false)
              onDownloadPdf()
            }}
          >
            <DownloadIcon className="h-4 w-4" />
            Télécharger le PDF
          </button>
        </div>
      </Modal>
    </>
  )
}
