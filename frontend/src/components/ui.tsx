import clsx from 'clsx'
import { useId, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { initialsOf } from '../lib/format'
import {
  AlertCircleIcon,
  AlertTriangleIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  CheckIcon,
  CopyIcon,
  InfoIcon,
  type IconComponent,
} from './icons'
import { LogoMark } from './Logo'

/* ---------------------------------------------------------------------------
 * En-tête de page
 * ------------------------------------------------------------------------- */

interface PageHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  eyebrow?: ReactNode
  actions?: ReactNode
  back?: { to: string; label: string }
}

export function PageHeader({ title, subtitle, eyebrow, actions, back }: PageHeaderProps) {
  return (
    <header className="animate-fade-in">
      {back && (
        <Link
          to={back.to}
          className="group mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition hover:text-slate-900"
        >
          <ArrowLeftIcon className="h-4 w-4 transition group-hover:-translate-x-0.5" />
          {back.label}
        </Link>
      )}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
          <h1 className="page-title text-balance">{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  )
}

/* ---------------------------------------------------------------------------
 * États vides / chargement
 * ------------------------------------------------------------------------- */

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: IconComponent
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={clsx('flex flex-col items-center px-6 py-12 text-center', className)}>
      <div className="relative">
        <div className="absolute inset-0 -z-10 scale-150 rounded-full bg-brand-100/60 blur-xl" />
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-[var(--shadow-card)] ring-1 ring-slate-200/80">
          <Icon className="h-6 w-6" />
        </div>
      </div>
      <p className="mt-5 font-display text-lg font-semibold text-slate-900">{title}</p>
      {description && <p className="mt-1.5 max-w-md text-sm leading-relaxed text-slate-500">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Chargement"
      className={clsx('inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent', className)}
    />
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('skeleton', className)} />
}

export function FullPageLoader({ label = 'Chargement…' }: { label?: string }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-slate-500">
      <LogoMark className="h-10 w-10 animate-pulse" />
      <p className="text-sm">{label}</p>
    </div>
  )
}

/* ---------------------------------------------------------------------------
 * Messages
 * ------------------------------------------------------------------------- */

type AlertTone = 'info' | 'success' | 'warning' | 'danger'

const ALERT_STYLES: Record<AlertTone, { box: string; icon: IconComponent; iconClass: string }> = {
  info: { box: 'border-brand-200 bg-brand-50/70 text-brand-900', icon: InfoIcon, iconClass: 'text-brand-500' },
  success: {
    box: 'border-emerald-200 bg-emerald-50/80 text-emerald-900',
    icon: CheckCircleIcon,
    iconClass: 'text-emerald-500',
  },
  warning: {
    box: 'border-amber-200 bg-amber-50/80 text-amber-900',
    icon: AlertTriangleIcon,
    iconClass: 'text-amber-500',
  },
  danger: { box: 'border-red-200 bg-red-50/80 text-red-900', icon: AlertCircleIcon, iconClass: 'text-red-500' },
}

export function Alert({
  tone = 'info',
  title,
  children,
  action,
  className,
}: {
  tone?: AlertTone
  title?: ReactNode
  children?: ReactNode
  action?: ReactNode
  className?: string
}) {
  const style = ALERT_STYLES[tone]
  const Icon = style.icon
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={clsx('flex gap-3 rounded-2xl border px-4 py-3.5 text-sm animate-fade-in', style.box, className)}
    >
      <Icon className={clsx('mt-0.5 h-[18px] w-[18px] shrink-0', style.iconClass)} />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={clsx('leading-relaxed', title && 'mt-0.5 opacity-90')}>{children}</div>}
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------------------
 * Progression
 * ------------------------------------------------------------------------- */

export function ProgressBar({
  percent,
  className,
  tone = 'brand',
  size = 'md',
}: {
  percent: number
  className?: string
  tone?: 'brand' | 'emerald' | 'amber' | 'red' | 'light'
  size?: 'sm' | 'md'
}) {
  const value = Math.min(100, Math.max(0, percent))
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={clsx(
        'w-full overflow-hidden rounded-full',
        size === 'sm' ? 'h-1.5' : 'h-2',
        tone === 'light' ? 'bg-white/10' : 'bg-slate-200/80',
        className,
      )}
    >
      <div
        className={clsx(
          'h-full rounded-full transition-[width] duration-700 ease-out',
          tone === 'brand' && 'bg-gradient-to-r from-brand-500 to-violet-500',
          tone === 'emerald' && 'bg-emerald-500',
          tone === 'amber' && 'bg-amber-500',
          tone === 'red' && 'bg-red-500',
          tone === 'light' && 'bg-gradient-to-r from-brand-300 to-amber-300',
        )}
        style={{ width: `${value}%` }}
      />
    </div>
  )
}

export function ProgressRing({
  percent,
  size = 120,
  stroke = 10,
  children,
}: {
  percent: number
  size?: number
  stroke?: number
  children?: ReactNode
}) {
  const gradientId = useId()
  const value = Math.min(100, Math.max(0, percent))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#8b5cf6" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="#e2e8f0" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={`url(#${gradientId})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - value / 100)}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">{children}</div>
    </div>
  )
}

/* ---------------------------------------------------------------------------
 * Divers
 * ------------------------------------------------------------------------- */

const AVATAR_TONES = [
  'bg-brand-100 text-brand-700',
  'bg-amber-100 text-amber-800',
  'bg-emerald-100 text-emerald-700',
  'bg-rose-100 text-rose-700',
  'bg-sky-100 text-sky-700',
  'bg-violet-100 text-violet-700',
]

export function Avatar({ name, size = 'md', className }: { name: string; size?: 'sm' | 'md' | 'lg'; className?: string }) {
  const tone = AVATAR_TONES[[...name].reduce((sum, char) => sum + char.charCodeAt(0), 0) % AVATAR_TONES.length]
  return (
    <span
      aria-hidden="true"
      className={clsx(
        'inline-flex shrink-0 items-center justify-center rounded-full font-semibold',
        size === 'sm' && 'h-8 w-8 text-xs',
        size === 'md' && 'h-10 w-10 text-sm',
        size === 'lg' && 'h-14 w-14 text-lg',
        tone,
        className,
      )}
    >
      {initialsOf(name)}
    </span>
  )
}

export function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  tone = 'brand',
}: {
  icon: IconComponent
  label: string
  value: ReactNode
  hint?: ReactNode
  tone?: 'brand' | 'amber' | 'emerald' | 'rose'
}) {
  return (
    <div className="card relative overflow-hidden !p-5">
      <div
        className={clsx(
          'mb-4 flex h-10 w-10 items-center justify-center rounded-xl',
          tone === 'brand' && 'bg-brand-50 text-brand-600',
          tone === 'amber' && 'bg-amber-50 text-amber-600',
          tone === 'emerald' && 'bg-emerald-50 text-emerald-600',
          tone === 'rose' && 'bg-rose-50 text-rose-600',
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <p className="text-[13px] font-medium text-slate-500">{label}</p>
      <p className="mt-1 font-display text-[28px] leading-none font-semibold text-slate-900 tabular-nums">{value}</p>
      {hint && <div className="mt-2 text-xs text-slate-500">{hint}</div>}
    </div>
  )
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  className,
}: {
  options: { value: T; label: ReactNode }[]
  value: T
  onChange: (value: T) => void
  className?: string
}) {
  return (
    <div role="tablist" className={clsx('inline-flex rounded-xl bg-slate-100 p-1', className)}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={value === option.value}
          onClick={() => onChange(option.value)}
          className={clsx(
            'inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-semibold whitespace-nowrap transition',
            value === option.value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function Switch({
  checked,
  onChange,
  label,
  description,
  id,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description?: string
  id: string
}) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-3">
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={clsx(
          'relative mt-0.5 inline-flex h-6 w-11 shrink-0 rounded-full transition',
          checked ? 'bg-brand-600' : 'bg-slate-300',
        )}
      >
        <span
          className={clsx(
            'absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform',
            checked && 'translate-x-5',
          )}
        />
      </button>
      <span>
        <span className="block text-sm font-medium text-slate-800">{label}</span>
        {description && <span className="block text-xs text-slate-500">{description}</span>}
      </span>
    </label>
  )
}

export function CopyButton({ text, label = 'Copier', className }: { text: string; label?: string; className?: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Contexte non sécurisé / permission refusée : repli via une zone de texte temporaire.
      const area = document.createElement('textarea')
      area.value = text
      document.body.appendChild(area)
      area.select()
      document.execCommand('copy')
      area.remove()
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  return (
    <button type="button" onClick={() => void copy()} className={clsx('btn-secondary btn-sm', className)}>
      {copied ? <CheckIcon className="h-4 w-4 text-emerald-600" /> : <CopyIcon className="h-4 w-4" />}
      {copied ? 'Copié' : label}
    </button>
  )
}
