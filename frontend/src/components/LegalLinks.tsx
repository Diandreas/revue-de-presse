import clsx from 'clsx'
import { Link } from 'react-router-dom'
import { LEGAL_ROUTES } from '../lib/legal'

/** Liens vers les CGU/CGV, la politique de confidentialité et les mentions légales
 * (pied de page public, écrans de connexion, barre latérale de l'application). */
export function LegalLinks({
  tone = 'dark',
  className,
  onNavigate,
}: {
  /** `dark` : texte gris sur fond clair · `light` : sur fond sombre (barre latérale). */
  tone?: 'dark' | 'light'
  className?: string
  onNavigate?: () => void
}) {
  return (
    <nav aria-label="Informations légales" className={className}>
      <ul className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-xs">
        {LEGAL_ROUTES.map((route) => (
          <li key={route.to}>
            <Link
              to={route.to}
              onClick={onNavigate}
              className={clsx(
                'underline-offset-2 transition hover:underline',
                tone === 'light' ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-800',
              )}
            >
              {route.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}
