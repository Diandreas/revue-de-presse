import { Component, type ErrorInfo, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { isChunkLoadError, reloadOnceForNewVersion } from '../lib/chunkReload'
import { AlertTriangleIcon, RefreshIcon } from './icons'
import { LogoMark } from './Logo'
import { WhatsAppButton } from './WhatsAppButton'

interface ErrorBoundaryProps {
  children: ReactNode
  /** Quand cette valeur change (ex : changement de page), l'erreur affichée est oubliée. */
  resetKey?: string
}

interface ErrorBoundaryState {
  error: unknown
  resetKey?: string
}

/** Évite la page blanche : une erreur de rendu affiche un message clair avec « Recharger ».
 * Une page introuvable après un déploiement (ancien fichier JS) recharge d'elle-même, une fois. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, resetKey: this.props.resetKey }

  static getDerivedStateFromError(error: unknown): Partial<ErrorBoundaryState> {
    return { error: error ?? new Error('Erreur inconnue') }
  }

  static getDerivedStateFromProps(props: ErrorBoundaryProps, state: ErrorBoundaryState): Partial<ErrorBoundaryState> | null {
    // Nouvelle page : on retente l'affichage au lieu de garder l'écran d'erreur.
    return props.resetKey !== state.resetKey ? { error: null, resetKey: props.resetKey } : null
  }

  componentDidCatch(error: unknown, info: ErrorInfo) {
    if (isChunkLoadError(error) && reloadOnceForNewVersion()) return
    console.error('Erreur d’affichage interceptée :', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return <ErrorScreen newVersion={isChunkLoadError(this.state.error)} />
  }
}

/** Variante à placer sous le routeur : changer de page efface l'erreur. */
export function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const location = useLocation()
  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>
}

function ErrorScreen({ newVersion }: { newVersion: boolean }) {
  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4 py-12">
      <div role="alert" className="card w-full max-w-md text-center">
        <LogoMark className="mx-auto h-10 w-10" />
        <div className="mx-auto mt-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-amber-600">
          <AlertTriangleIcon className="h-6 w-6" />
        </div>
        <h1 className="mt-4 font-display text-xl font-semibold text-slate-900">
          {newVersion ? 'Une nouvelle version est disponible' : 'Cette page a rencontré un problème'}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-slate-500">
          {newVersion
            ? 'L’application a été mise à jour pendant que cette page était ouverte. Rechargez la page pour continuer.'
            : 'Une erreur inattendue a interrompu l’affichage. Vos revues et vos documents ne sont pas perdus : rechargez la page pour continuer.'}
        </p>
        <div className="mt-6 flex flex-col items-center gap-3">
          <button type="button" className="btn-primary w-full sm:w-auto" onClick={() => window.location.reload()}>
            <RefreshIcon className="h-4 w-4" />
            Recharger la page
          </button>
          <a href="/" className="text-sm font-medium text-slate-500 transition hover:text-slate-900">
            Revenir à l’accueil
          </a>
        </div>
        {!newVersion && (
          <p className="mt-6 border-t border-slate-100 pt-4 text-sm text-slate-500">
            Le problème persiste ?{' '}
            <WhatsAppButton topic="help" variant="link" label="Écrivez-nous sur WhatsApp" className="align-middle" />
          </p>
        )}
      </div>
    </div>
  )
}
