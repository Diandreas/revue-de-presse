import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/** Pages publiques : à chaque navigation, défile jusqu'à l'ancre demandée (« /#tarifs »,
 * « /cgu#ia ») ou revient en haut de page — le routeur ne le fait pas seul. */
export function useScrollToHash() {
  const { pathname, hash } = useLocation()

  useEffect(() => {
    const target = hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null
    if (target) target.scrollIntoView()
    else window.scrollTo({ top: 0 })
  }, [pathname, hash])
}
