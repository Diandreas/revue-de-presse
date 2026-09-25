/** Jeu d'icônes minimal, en SVG inline (pas de dépendance) — trait 1.75, style cohérent. */
import type { SVGProps } from 'react'

function Icon({ children, ...props }: SVGProps<SVGSVGElement> & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  )
}

export const NewspaperIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M4 4h13a3 3 0 0 1 3 3v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4Z" />
    <path d="M17 21a2 2 0 0 0 2-2V8h-2" />
    <path d="M8 8h6M8 12h6M8 16h4" />
  </Icon>
)

export const UploadCloudIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M7 17a4.5 4.5 0 0 1-1-8.9A5.5 5.5 0 0 1 16.9 6.5 4.5 4.5 0 0 1 17 17" />
    <path d="M12 12v7M9 16l3-3 3 3" />
  </Icon>
)

export const TagIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 2 3 11v6a2 2 0 0 0 2 2h6l9-9V4a2 2 0 0 0-2-2Z" />
    <circle cx="8.5" cy="7.5" r="1.25" fill="currentColor" stroke="none" />
  </Icon>
)

export const UsersIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <circle cx="9" cy="8" r="3" />
    <path d="M3 20c0-3 2.5-5 6-5s6 2 6 5" />
    <path d="M16 4.5a3 3 0 0 1 0 5.9M20 20c0-2.5-1.7-4.4-4-4.9" />
  </Icon>
)

export const CreditCardIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <rect x="2.5" y="5" width="19" height="14" rx="2.5" />
    <path d="M2.5 10h19M6 15h4" />
  </Icon>
)

export const SettingsIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2.5v3M12 18.5v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2.5 12h3M18.5 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
  </Icon>
)

export const LogOutIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3" />
    <path d="M15 16l4-4-4-4M19 12H8" />
  </Icon>
)

export const CheckCircleIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8.5 12.5l2.3 2.3L15.5 9.5" />
  </Icon>
)

export const AlertTriangleIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 3.5 21 19.5H3Z" />
    <path d="M12 9.5v4M12 16.5h.01" />
  </Icon>
)

export const LoaderIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon className="animate-spin" {...p}>
    <path d="M12 3a9 9 0 1 0 9 9" />
  </Icon>
)

export const FileTextIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M7 3h7l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
    <path d="M14 3v4h4M9 12h6M9 15.5h6M9 8.5h2" />
  </Icon>
)

export const ImageIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <circle cx="8.5" cy="9.5" r="1.5" />
    <path d="M21 16l-5-5-9 9" />
  </Icon>
)

export const ArrowRightIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Icon>
)

export const SparkleIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
    <path d="M12 8a4 4 0 0 0 4 4 4 4 0 0 0-4 4 4 4 0 0 0-4-4 4 4 0 0 0 4-4Z" />
  </Icon>
)

export const ShieldIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6Z" />
    <path d="M9.5 12l1.8 1.8L14.5 10" />
  </Icon>
)
