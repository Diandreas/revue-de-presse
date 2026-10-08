import clsx from 'clsx'
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import { AlertCircleIcon, CheckCircleIcon, InfoIcon, XIcon } from './icons'

type ToastTone = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  tone: ToastTone
  message: string
}

interface ToastApi {
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

const DURATION_MS = 4500

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setToasts((items) => items.filter((t) => t.id !== id)), [])

  const push = useCallback(
    (tone: ToastTone, message: string) => {
      const id = nextId.current++
      setToasts((items) => [...items.slice(-3), { id, tone, message }])
      window.setTimeout(() => dismiss(id), DURATION_MS)
    },
    [dismiss],
  )

  const api = useMemo<ToastApi>(
    () => ({
      success: (message) => push('success', message),
      error: (message) => push('error', message),
      info: (message) => push('info', message),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:items-end sm:p-6"
      >
        {toasts.map((toast) => {
          const Icon = toast.tone === 'success' ? CheckCircleIcon : toast.tone === 'error' ? AlertCircleIcon : InfoIcon
          return (
            <div
              key={toast.id}
              className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl bg-ink-900 px-4 py-3.5 text-sm text-white shadow-2xl ring-1 ring-white/10 animate-slide-up"
            >
              <Icon
                className={clsx(
                  'mt-0.5 h-[18px] w-[18px] shrink-0',
                  toast.tone === 'success' && 'text-emerald-400',
                  toast.tone === 'error' && 'text-red-400',
                  toast.tone === 'info' && 'text-brand-300',
                )}
              />
              <p className="flex-1 leading-relaxed">{toast.message}</p>
              <button
                type="button"
                aria-label="Fermer"
                onClick={() => dismiss(toast.id)}
                className="-mr-1 rounded-md p-0.5 text-white/50 transition hover:text-white"
              >
                <XIcon className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast doit être utilisé à l’intérieur de <ToastProvider>.')
  return ctx
}
