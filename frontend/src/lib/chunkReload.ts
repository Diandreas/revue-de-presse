/** Après un déploiement, les fichiers JS de l'ancienne version disparaissent : un onglet
 * resté ouvert échoue alors à charger la page suivante (pages chargées à la demande).
 * On recharge une fois pour récupérer la nouvelle version, sans jamais boucler si le
 * problème persiste (réseau coupé, serveur en panne). */

const RELOAD_KEY = 'rdp:chunk-reload-at'
const MIN_DELAY_BETWEEN_RELOADS_MS = 60_000

const CHUNK_ERROR_PATTERNS = [
  /failed to fetch dynamically imported module/i,
  /error loading dynamically imported module/i,
  /importing a module script failed/i,
  /unable to preload css/i,
  /loading (css )?chunk [\w-]+ failed/i,
]

export function isChunkLoadError(error: unknown): boolean {
  if (!error) return false
  const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
  return CHUNK_ERROR_PATTERNS.some((pattern) => pattern.test(message))
}

function lastReloadAt(): number {
  try {
    return Number(window.sessionStorage.getItem(RELOAD_KEY)) || 0
  } catch {
    return 0
  }
}

/** Recharge la page si aucun rechargement automatique n'a eu lieu depuis une minute.
 * Renvoie false si on s'abstient (l'appelant affiche alors son message d'erreur). */
export function reloadOnceForNewVersion(): boolean {
  if (Date.now() - lastReloadAt() < MIN_DELAY_BETWEEN_RELOADS_MS) return false
  try {
    window.sessionStorage.setItem(RELOAD_KEY, String(Date.now()))
  } catch {
    // Stockage indisponible (navigation privée stricte) : on ne peut pas garantir
    // l'absence de boucle, donc pas de rechargement automatique.
    return false
  }
  window.location.reload()
  return true
}

/** Vite émet `vite:preloadError` quand un import dynamique échoue (cf. doc Vite,
 * « Load error handling ») : on tente le rechargement avant que l'erreur n'atteigne React. */
export function installChunkReloadHandler() {
  window.addEventListener('vite:preloadError', (event) => {
    if (reloadOnceForNewVersion()) event.preventDefault()
  })
}
