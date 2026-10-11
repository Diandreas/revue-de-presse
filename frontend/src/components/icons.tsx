/** Jeu d'icônes en SVG inline (aucune dépendance) — trait 1.75, angles arrondis, style cohérent. */
import type { ReactNode, SVGProps } from 'react'

export type IconProps = SVGProps<SVGSVGElement>
export type IconComponent = (props: IconProps) => ReactNode

function Icon({ children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  )
}

export const NewspaperIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 4h13a3 3 0 0 1 3 3v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4Z" />
    <path d="M17 21a2 2 0 0 0 2-2V8h-2" />
    <path d="M8 8h6M8 12h6M8 16h4" />
  </Icon>
)

export const UploadCloudIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M7 17a4.5 4.5 0 0 1-1-8.9A5.5 5.5 0 0 1 16.9 6.5 4.5 4.5 0 0 1 17 17" />
    <path d="M12 12v8M9 15l3-3 3 3" />
  </Icon>
)

export const TagIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12.6 2.6 21 11a2 2 0 0 1 0 2.8L13.8 21a2 2 0 0 1-2.8 0L2.6 12.6A2 2 0 0 1 2 11.2V4a2 2 0 0 1 2-2h7.2a2 2 0 0 1 1.4.6Z" />
    <circle cx="7.5" cy="7.5" r="1.4" fill="currentColor" stroke="none" />
  </Icon>
)

export const UsersIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="9" cy="8" r="3.2" />
    <path d="M3 20c0-3.2 2.7-5.5 6-5.5s6 2.3 6 5.5" />
    <path d="M16 4.6a3.2 3.2 0 0 1 0 6.3M21 20c0-2.6-1.7-4.6-4.2-5.2" />
  </Icon>
)

export const UserIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
  </Icon>
)

export const CreditCardIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="2.5" y="5" width="19" height="14" rx="2.5" />
    <path d="M2.5 10h19M6 15h4" />
  </Icon>
)

export const SettingsIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10.3 3.4a1.8 1.8 0 0 1 3.4 0l.3.9a1.8 1.8 0 0 0 2.6 1l.8-.5a1.8 1.8 0 0 1 2.4 2.4l-.5.8a1.8 1.8 0 0 0 1 2.6l.9.3a1.8 1.8 0 0 1 0 3.4l-.9.3a1.8 1.8 0 0 0-1 2.6l.5.8a1.8 1.8 0 0 1-2.4 2.4l-.8-.5a1.8 1.8 0 0 0-2.6 1l-.3.9a1.8 1.8 0 0 1-3.4 0l-.3-.9a1.8 1.8 0 0 0-2.6-1l-.8.5a1.8 1.8 0 0 1-2.4-2.4l.5-.8a1.8 1.8 0 0 0-1-2.6l-.9-.3a1.8 1.8 0 0 1 0-3.4l.9-.3a1.8 1.8 0 0 0 1-2.6l-.5-.8a1.8 1.8 0 0 1 2.4-2.4l.8.5a1.8 1.8 0 0 0 2.6-1Z" />
    <circle cx="12" cy="12" r="3" />
  </Icon>
)

export const LogOutIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3" />
    <path d="M15 16l4-4-4-4M19 12H9" />
  </Icon>
)

export const MenuIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 6.5h16M4 12h16M4 17.5h16" />
  </Icon>
)

export const XIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Icon>
)

export const ChevronRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M9 6l6 6-6 6" />
  </Icon>
)

export const ChevronDownIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 9l6 6 6-6" />
  </Icon>
)

export const ArrowLeftIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M19 12H5M11 18l-6-6 6-6" />
  </Icon>
)

export const ArrowRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Icon>
)

export const PlusIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
)

export const CheckIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Icon>
)

export const CheckCircleIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8.5 12.5l2.3 2.3L15.5 9.5" />
  </Icon>
)

export const AlertTriangleIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10.3 4.2 2.6 17.5a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z" />
    <path d="M12 9.5v4M12 17h.01" />
  </Icon>
)

export const AlertCircleIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5.5M12 16.5h.01" />
  </Icon>
)

export const InfoIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5.5M12 7.5h.01" />
  </Icon>
)

export const LoaderIcon = ({ className, ...p }: IconProps) => (
  <Icon className={['animate-spin', className].filter(Boolean).join(' ')} {...p}>
    <path d="M12 3a9 9 0 1 0 9 9" />
  </Icon>
)

export const FileTextIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M7 3h7l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
    <path d="M14 3v4h4M9 12h6M9 15.5h6M9 8.5h2" />
  </Icon>
)

export const ImageIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2.5" />
    <circle cx="8.5" cy="9.5" r="1.6" />
    <path d="M21 16l-5-5-9 9" />
  </Icon>
)

export const CameraIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.3l1.4-2h5.6l1.4 2h1.3A2.5 2.5 0 0 1 20 8.5v8a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 16.5Z" />
    <circle cx="12" cy="12.5" r="3.2" />
  </Icon>
)

export const TrashIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" />
  </Icon>
)

export const CopyIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="8.5" y="8.5" width="12" height="12" rx="2" />
    <path d="M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5" />
  </Icon>
)

export const LinkIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" />
    <path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />
  </Icon>
)

export const RefreshIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 11a8 8 0 0 0-14.9-3.5M4 4v3.5h3.5" />
    <path d="M4 13a8 8 0 0 0 14.9 3.5M20 20v-3.5h-3.5" />
  </Icon>
)

export const DownloadIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
  </Icon>
)

export const ClockIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Icon>
)

export const CalendarIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3.5" y="5" width="17" height="16" rx="2.5" />
    <path d="M8 3v4M16 3v4M3.5 10h17" />
  </Icon>
)

export const SparkleIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3.5c.5 3.9 2.6 6 6.5 6.5-3.9.5-6 2.6-6.5 6.5-.5-3.9-2.6-6-6.5-6.5 3.9-.5 6-2.6 6.5-6.5Z" />
    <path d="M19 15.5c.2 1.6 1 2.4 2.5 2.5-1.6.2-2.4 1-2.5 2.5-.2-1.6-1-2.4-2.5-2.5 1.6-.2 2.4-1 2.5-2.5Z" />
  </Icon>
)

export const ShieldIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6Z" />
    <path d="M9.5 12l1.8 1.8L14.5 10" />
  </Icon>
)

export const ScaleIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3v18M7 21h10M4.5 7h15" />
    <path d="M6.5 7 3.5 14a3 3 0 0 0 6 0Z" />
    <path d="M17.5 7l-3 7a3 3 0 0 0 6 0Z" />
  </Icon>
)

export const StarIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3.5l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8Z" />
  </Icon>
)

export const FlagIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 21V4M5 4h12l-2.5 4L17 12H5" />
  </Icon>
)

export const EyeIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7S2.5 12 2.5 12Z" />
    <circle cx="12" cy="12" r="3" />
  </Icon>
)

export const EyeOffIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 3l18 18" />
    <path d="M10.6 6.1A9.8 9.8 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-2.8 3.5M6.3 7.3C3.8 9 2.5 12 2.5 12S6 18 12 18c1.7 0 3.2-.4 4.5-1.1" />
    <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
  </Icon>
)

export const MailIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2.5" />
    <path d="M3.5 7.5l8.5 6 8.5-6" />
  </Icon>
)

export const LockIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="5" y="11" width="14" height="10" rx="2.5" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </Icon>
)

export const ZapIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M13 3 4.5 13.5H11l-1 7.5 8.5-10.5H12Z" />
  </Icon>
)

export const BarChartIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 20h16M7 16v-5M12 16V7M17 16v-8" />
  </Icon>
)

export const BuildingIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M16 9h2a2 2 0 0 1 2 2v10M8 7h4M8 11h4M8 15h4M3 21h18" />
  </Icon>
)

export const SmartphoneIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="7" y="2.5" width="10" height="19" rx="2.5" />
    <path d="M11 18.5h2" />
  </Icon>
)

export const LandmarkIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 21h18M4.5 10h15M12 3 3.5 8h17Z" />
    <path d="M6.5 10v8M10.5 10v8M13.5 10v8M17.5 10v8" />
  </Icon>
)

export const HighlighterIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M15 3.5l5.5 5.5-8.5 8.5H6.5V12Z" />
    <path d="M6.5 17.5 4 20h5" />
    <path d="M12 7l5 5" />
  </Icon>
)

export const ScanTextIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" />
    <path d="M8 9h8M8 12h8M8 15h5" />
  </Icon>
)

export const PenLineIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </Icon>
)

export const LayersIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3 2.5 8 12 13l9.5-5Z" />
    <path d="M2.5 12.5 12 17.5l9.5-5" />
    <path d="M2.5 16.5 12 21.5l9.5-5" />
  </Icon>
)

export const GiftIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="8" width="18" height="4" rx="1" />
    <path d="M5 12v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-8M12 8v13" />
    <path d="M12 8S9.8 3.5 7.6 4.6 8.6 8 12 8Zm0 0s2.2-4.5 4.4-3.4S15.4 8 12 8Z" />
  </Icon>
)

export const LayoutDashboardIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="3" width="7.5" height="9" rx="1.8" />
    <rect x="13.5" y="3" width="7.5" height="5.5" rx="1.8" />
    <rect x="13.5" y="11.5" width="7.5" height="9.5" rx="1.8" />
    <rect x="3" y="15" width="7.5" height="6" rx="1.8" />
  </Icon>
)

export const ExternalLinkIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14 4h6v6M10 14 20 4M19 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4" />
  </Icon>
)

export const InboxIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 13h5l1.5 3h5L16 13h5" />
    <path d="M5.5 5h13L21 13v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5Z" />
  </Icon>
)

export const QuoteIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M7 6.5C4.8 7.6 3.5 9.6 3.5 12.5V17h5.5v-5.5H6c0-1.8.7-3 2.2-3.9Z" />
    <path d="M17.5 6.5c-2.2 1.1-3.5 3.1-3.5 6V17h5.5v-5.5h-3c0-1.8.7-3 2.2-3.9Z" />
  </Icon>
)

export const LightbulbIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M9 18h6M10 21.5h4" />
    <path d="M12 2.5a6.5 6.5 0 0 0-3.9 11.7c.6.5.9 1.2.9 2V16.5h6v-.3c0-.8.3-1.5.9-2A6.5 6.5 0 0 0 12 2.5Z" />
  </Icon>
)

export const SearchIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="M20.5 20.5 16 16" />
  </Icon>
)

/** Bulle de discussion avec combiné : le geste « écrire sur WhatsApp », dans le style du jeu. */
export const WhatsAppIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M7.9 20A9 9 0 1 0 4 16.1L2.5 21.5Z" />
    <path d="M9.4 8.6c.3-.3.8-.3 1.1 0l.9.9c.3.3.3.8 0 1.1l-.5.5c.4.9 1.1 1.6 2 2l.5-.5c.3-.3.8-.3 1.1 0l.9.9c.3.3.3.8 0 1.1l-.5.5c-.6.6-1.5.8-2.3.4a8.4 8.4 0 0 1-4-4c-.4-.8-.2-1.7.4-2.3Z" />
  </Icon>
)
