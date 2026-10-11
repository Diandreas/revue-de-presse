import clsx from 'clsx'
import { whatsappUrl, WHATSAPP_DISPLAY, type WhatsAppTopic } from '../lib/contact'
import { WhatsAppIcon } from './icons'

interface WhatsAppButtonProps {
  topic: WhatsAppTopic
  organizationName?: string | null
  label?: string
  /** `light` : bouton blanc (fond clair) · `dark` : sur fond sombre (barre latérale) · `link` : lien discret ·
   * `primary` : appel à l'action principal de la page. */
  variant?: 'light' | 'dark' | 'link' | 'primary'
  className?: string
  showNumber?: boolean
}

/** Ouvre une conversation WhatsApp avec l'équipe, message pré-rempli selon le contexte. */
export function WhatsAppButton({
  topic,
  organizationName,
  label = 'Demander une démo sur WhatsApp',
  variant = 'light',
  className,
  showNumber = false,
}: WhatsAppButtonProps) {
  return (
    <a
      href={whatsappUrl(topic, organizationName)}
      target="_blank"
      rel="noopener noreferrer"
      className={clsx(
        variant === 'light' && 'btn-secondary',
        variant === 'dark' &&
          'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-300 transition hover:bg-white/5 hover:text-white',
        variant === 'link' && 'inline-flex items-center gap-1.5 font-semibold text-emerald-700 hover:text-emerald-800',
        variant === 'primary' && 'btn-primary',
        className,
      )}
    >
      <WhatsAppIcon
        className={clsx(
          'shrink-0',
          variant === 'link' ? 'h-4 w-4' : 'h-[18px] w-[18px]',
          variant === 'primary' ? 'text-white' : 'text-emerald-500',
        )}
      />
      <span className="truncate">{label}</span>
      {showNumber && <span className="font-normal text-slate-500">· {WHATSAPP_DISPLAY}</span>}
    </a>
  )
}
