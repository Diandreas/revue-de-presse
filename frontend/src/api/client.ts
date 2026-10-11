import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiErrorBody } from './types'

const baseURL = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api`

export const apiClient = axios.create({ baseURL, withCredentials: true })

let accessToken: string | null = null
let refreshPromise: Promise<string | null> | null = null
let onUnauthorized: (() => void) | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

/* Organisation courante : un compte peut appartenir à plusieurs organisations. Celle choisie
 * est envoyée dans l'en-tête X-Organization-Id de chaque requête et mémorisée dans le
 * navigateur (retrouvée à la prochaine visite). */
const ORGANIZATION_STORAGE_KEY = 'revue-de-presse.organization'
/** Codes renvoyés par l'API quand l'organisation demandée n'est plus accessible (membre
 * retiré, organisation fermée) ou doit être choisie (cf. backend core/permissions.py). */
const ORGANIZATION_ERROR_CODES = ['organization_required', 'organization_access_lost', 'no_organization']

function readStoredOrganizationId(): string | null {
  try {
    return window.localStorage.getItem(ORGANIZATION_STORAGE_KEY)
  } catch {
    return null // stockage indisponible (navigation privée stricte…)
  }
}

let organizationId: string | null = readStoredOrganizationId()
let onOrganizationLost: (() => void) | null = null

export function getOrganizationId() {
  return organizationId
}

export function setOrganizationId(id: string | null) {
  organizationId = id
  try {
    if (id) window.localStorage.setItem(ORGANIZATION_STORAGE_KEY, id)
    else window.localStorage.removeItem(ORGANIZATION_STORAGE_KEY)
  } catch {
    // Stockage indisponible : le choix vaut pour cet onglet seulement.
  }
}

export function setOrganizationLostHandler(handler: () => void) {
  onOrganizationLost = handler
}

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.set('Authorization', `Bearer ${accessToken}`)
  }
  if (organizationId) {
    config.headers.set('X-Organization-Id', organizationId)
  }
  return config
})

/** Un seul appel de refresh en vol à la fois (évite une rafale de requêtes /refresh/
 * si plusieurs requêtes échouent en 401 simultanément). */
export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = apiClient
      .post<{ access?: string } | ''>('/auth/token/refresh/')
      .then((res) => {
        // 204 sans corps = aucune session à reprendre (visiteur non connecté).
        accessToken = (res.data && typeof res.data === 'object' && res.data.access) || null
        return accessToken
      })
      .catch(() => {
        accessToken = null
        return null
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean }

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined
    const isAuthEndpoint = original?.url?.includes('/auth/token/')

    if (error.response?.status === 401 && original && !original._retry && !isAuthEndpoint) {
      original._retry = true
      const newToken = await refreshAccessToken()
      if (newToken) {
        original.headers.set('Authorization', `Bearer ${newToken}`)
        return apiClient(original)
      }
      onUnauthorized?.()
    }
    const code = (error.response?.data as ApiErrorBody | undefined)?.code
    if (code && ORGANIZATION_ERROR_CODES.includes(code)) {
      // Membre retiré, organisation fermée… : on recharge la liste des organisations au lieu
      // de laisser l'appli à moitié ouverte.
      onOrganizationLost?.()
    }
    return Promise.reject(error)
  },
)

/** Premier message lisible d'une erreur de validation DRF ({champ: ["msg"]} ou ["msg"]). */
function firstValidationMessage(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = firstValidationMessage(item)
      if (message) return message
    }
  } else if (value && typeof value === 'object') {
    for (const item of Object.values(value)) {
      const message = firstValidationMessage(item)
      if (message) return message
    }
  }
  return null
}

export function extractErrorMessage(error: unknown, fallback = 'Une erreur est survenue.'): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return 'Connexion impossible au serveur. Vérifiez votre connexion internet puis réessayez.'
    }
    if (error.response.status === 413) return 'Fichier trop volumineux (30 Mo maximum).'
    const data = error.response.data as ApiErrorBody | undefined
    // Erreurs par champ : le message précis (« Adresse email invalide ») plutôt que le
    // générique « Une erreur de validation est survenue ».
    const validation = data?.errors ? firstValidationMessage(data.errors) : null
    if (validation) return validation
    if (data?.detail) return data.detail
  }
  return fallback
}
