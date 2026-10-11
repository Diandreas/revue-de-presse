/** Diffusion de la revue : partage natif (Web Share API, qui ouvre WhatsApp, Gmail… sur
 * mobile) avec le PDF en pièce jointe quand le navigateur le permet ; sinon un lien
 * WhatsApp avec le texte de la revue. */

/** Le navigateur sait-il partager un fichier (PDF) via la feuille de partage du système ? */
export function canShareFiles(): boolean {
  if (typeof navigator === 'undefined' || typeof navigator.share !== 'function' || typeof navigator.canShare !== 'function') {
    return false
  }
  try {
    return navigator.canShare({ files: [new File(['%PDF'], 'revue.pdf', { type: 'application/pdf' })] })
  } catch {
    return false
  }
}

/** Partage natif de texte seul (navigateurs sans partage de fichiers). */
export function canShareText(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.share === 'function'
}

/** Au-delà, certains téléphones tronquent le texte passé à WhatsApp par lien : on conseille le PDF. */
export const WHATSAPP_TEXT_SOFT_LIMIT = 4000

/** Lien « click to chat » sans destinataire : WhatsApp demande à qui envoyer le texte. */
export function whatsappShareUrl(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`
}

/** Erreur levée par navigator.share quand l'utilisateur ferme la feuille de partage. */
export function isShareCancelled(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

/** Partage refusé faute de geste récent de l'utilisateur (le PDF a mis trop longtemps à se
 * préparer) : il suffit de toucher à nouveau le bouton. */
export function isShareActivationLost(error: unknown) {
  return error instanceof DOMException && error.name === 'NotAllowedError'
}
