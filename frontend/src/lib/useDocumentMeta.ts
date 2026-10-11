import { useEffect } from 'react'

/** Titre d'onglet et description (moteurs de recherche) propres à une page publique ;
 * les valeurs d'index.html sont rétablies en quittant la page. */
export function useDocumentMeta(title: string, description?: string) {
  useEffect(() => {
    const previousTitle = document.title
    document.title = title

    const meta = document.querySelector<HTMLMetaElement>('meta[name="description"]')
    const previousDescription = meta?.content
    if (meta && description) meta.content = description

    return () => {
      document.title = previousTitle
      if (meta && previousDescription !== undefined) meta.content = previousDescription
    }
  }, [title, description])
}
