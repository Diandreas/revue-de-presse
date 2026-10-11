import { useAuth } from '../auth/useAuth'
import { AuthShell } from './AuthShell'
import { LogOutIcon, MailIcon } from './icons'
import { Alert } from './ui'
import { WhatsAppButton } from './WhatsAppButton'

/** Compte connecté qui n'a plus aucune organisation active : retiré de l'équipe, départ
 * volontaire ou organisation fermée. Remplace l'appli « à moitié ouverte » (erreurs 403/404
 * sur chaque page). */
export function NoOrganizationScreen() {
  const { user, logout } = useAuth()

  return (
    <AuthShell
      title="Aucun espace disponible"
      subtitle={
        <>
          Le compte <strong className="text-slate-700">{user?.email}</strong> n’est plus rattaché à aucune
          organisation active : vous avez été retiré de l’équipe, vous l’avez quittée, ou l’organisation a été
          fermée.
        </>
      }
    >
      <div className="space-y-4">
        <Alert tone="info" title="Vous avez reçu une invitation ?">
          <span className="inline-flex items-start gap-1.5">
            <MailIcon className="mt-0.5 h-4 w-4 shrink-0" />
            Ouvrez simplement le lien d’invitation : vous rejoindrez l’équipe avec ce compte.
          </span>
        </Alert>
        <WhatsAppButton topic="help" label="Contacter l’équipe sur WhatsApp" className="w-full" />
        <button type="button" className="btn-secondary w-full" onClick={() => void logout()}>
          <LogOutIcon className="h-4 w-4" />
          Se déconnecter
        </button>
      </div>
    </AuthShell>
  )
}
