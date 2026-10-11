import { extractErrorMessage } from '../api/client'
import {
  useNotificationPreferences,
  useUpdateNotificationPreferences,
} from '../features/notifications/useNotificationPreferences'
import { MailIcon } from './icons'
import { useToast } from './Toast'
import { Skeleton, Switch } from './ui'

/** Encart « Notifications par e-mail » de la page Paramètres. */
export function NotificationPreferencesCard() {
  const toast = useToast()
  const preferences = useNotificationPreferences()
  const update = useUpdateNotificationPreferences()

  const toggle = async (checked: boolean) => {
    try {
      await update.mutateAsync({ email_review_updates: checked })
      toast.success(checked ? 'E-mails de revue activés.' : 'E-mails de revue désactivés.')
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Impossible d’enregistrer votre choix.'))
    }
  }

  return (
    <section className="card">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-600">
          <MailIcon className="h-5 w-5" />
        </span>
        <div>
          <h2 className="section-title">Notifications par e-mail</h2>
          <p className="text-xs text-slate-500">Les e-mails liés à votre compte et à l’abonnement restent envoyés.</p>
        </div>
      </div>
      <div className="mt-5">
        {preferences.isLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <Switch
            id="email-review-updates"
            checked={update.isPending ? !!update.variables?.email_review_updates : (preferences.data?.email_review_updates ?? true)}
            onChange={(checked) => void toggle(checked)}
            label="Revue prête ou en échec"
            description="Un e-mail avec le lien vers la revue quand l’analyse que vous avez lancée se termine."
          />
        )}
      </div>
    </section>
  )
}
