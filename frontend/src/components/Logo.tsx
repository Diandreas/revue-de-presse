import clsx from 'clsx'
import { useId } from 'react'

/** Marque : une page de journal dont une ligne est surlignée — le geste de base de la revue de presse. */
export function LogoMark({ className }: { className?: string }) {
  const gradientId = useId()
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true" className={clsx('shrink-0', className)}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="1" stopColor="#1e1b4b" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${gradientId})`} />
      <rect x="6.5" y="13.1" width="19" height="5.8" rx="1.6" fill="#fbbf24" />
      <path d="M9 9.6h14" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" opacity=".85" />
      <path d="M9 16h14" stroke="#1e1b4b" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M9 22.4h9" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" opacity=".85" />
    </svg>
  )
}

interface LogoProps {
  className?: string
  /** `light` : texte clair, pour les fonds sombres (barre latérale, panneau de marque). */
  tone?: 'dark' | 'light'
  subtitle?: string
}

export function Logo({ className, tone = 'dark', subtitle }: LogoProps) {
  return (
    <div className={clsx('flex items-center gap-2.5', className)}>
      <LogoMark className="h-9 w-9 drop-shadow-sm" />
      <div className="min-w-0 leading-tight">
        <p className={clsx('font-display text-[17px] font-semibold', tone === 'light' ? 'text-white' : 'text-slate-900')}>
          Revue de Presse
        </p>
        {subtitle && (
          <p className={clsx('truncate text-xs', tone === 'light' ? 'text-slate-400' : 'text-slate-500')}>{subtitle}</p>
        )}
      </div>
    </div>
  )
}
