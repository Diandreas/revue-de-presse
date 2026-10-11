export interface User {
  id: string
  email: string
  full_name: string
  date_joined: string
}

export type MembershipRole = 'owner' | 'admin' | 'member'

export interface Organization {
  id: string
  name: string
  slug: string
  country: string
  default_locale: string
  created_at: string
  /** Rôle de l'utilisateur connecté dans cette organisation. */
  my_role?: MembershipRole | null
}

export interface Invitation {
  id: string
  email: string
  role: MembershipRole
  status: 'pending' | 'accepted' | 'revoked'
  expires_at: string
  created_at: string
  accept_url: string
}

export interface Membership {
  id: string
  user: User
  role: MembershipRole
  /** Identifiant de l'organisation de cette adhésion. */
  organization?: string
  created_at: string
}

export type CategoryType = 'legal_risk' | 'important_point' | 'intox' | 'custom'

export interface DetectionCategory {
  id: string
  name: string
  type: CategoryType
  description: string
  prompt_hint: string
  keywords: string[]
  color: string
  is_active: boolean
  sort_order: number
  organization: string | null
}

export type ExtractionStatus = 'pending' | 'done' | 'failed'
export type SourceDocumentKind = 'pdf' | 'image'

export interface SourceDocument {
  id: string
  file: string
  original_filename: string
  kind: SourceDocumentKind
  page_count: number | null
  requires_ocr: boolean | null
  extraction_status: ExtractionStatus
  extraction_error: string
  job: string | null
  created_at: string
}

export type JobStatus =
  | 'UPLOADED'
  | 'TEXT_EXTRACTION'
  | 'CHUNKING_SUMMARIZATION'
  | 'HIGHLIGHT_DETECTION'
  | 'REVIEW_DRAFTING'
  | 'REVIEW_READY'
  | 'EXPORTED'
  | 'FAILED'

export interface PipelineStepRun {
  step_name: string
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  progress_percent: number
  result_summary: Record<string, unknown>
  error_message: string
  started_at: string | null
  finished_at: string | null
}

interface PressReviewJobBase {
  id: string
  title: string
  status: JobStatus
  progress_percent: number
  created_at: string
  completed_at: string | null
  /** Auteur de la revue (id utilisateur) : il peut la supprimer, comme un owner / admin. */
  created_by: string | null
}

export interface PressReviewJobListItem extends PressReviewJobBase {
  documents_count: number
  highlights_count: number
}

export interface PressReviewJobDetail extends PressReviewJobBase {
  error_message: string
  started_at: string | null
  step_runs: PipelineStepRun[]
  documents: SourceDocument[]
}

export interface JobStats {
  total: number
  active: number
  ready: number
  failed: number
  highlights: number
  documents: number
}

export interface Highlight {
  id: string
  category: DetectionCategory
  excerpt: string
  explanation: string
  confidence: number | null
  page_number: number | null
  order: number
  source_document: string | null
  /** Masqué par l'utilisateur (faux positif) : absent de l'annexe des exports. */
  hidden: boolean
}

/** Notice d'un journal dans la revue de presse. */
export interface PressReviewEntry {
  source: string
  headline: string
  summary: string
  documents: string[]
}

export interface PressReviewSection {
  key: string
  title: string
  color: string
  icon: string
  entries: PressReviewEntry[]
}

/** Revue au format « revue de presse » (bandeau, rubriques, une notice par journal). */
export interface StructuredReview {
  country: string
  date_label: string
  sections: PressReviewSection[]
}

/** Rubrique de la charte (toutes, même vides : pour y déplacer une notice). */
export interface PressReviewRubrique {
  key: string
  title: string
  color: string
  icon: string
}

export interface GeneratedReview {
  summary_markdown: string
  /** null pour les revues générées avant ce format (affichées en Markdown). */
  structured: StructuredReview | null
  pdf_file: string | null
  docx_file: string | null
  generated_at: string | null
  /** Corrigée à la main : la version de l'IA peut être restaurée. */
  is_edited: boolean
  edited_at: string | null
  edited_by_name: string | null
  rubriques: PressReviewRubrique[]
}

/** Correction de la revue (PATCH /jobs/{id}/review/). */
export interface ReviewUpdateInput {
  title?: string
  date_label?: string
  sections?: { key: string; entries: PressReviewEntry[] }[]
  /** Dernière correction connue : 409 si un autre membre a corrigé entre-temps. */
  expected_edited_at?: string | null
}

export interface Plan {
  id: string
  code: string
  name: string
  /** Toujours null côté client : formules « sur devis » (prix visible du seul staff). */
  price_amount: string | null
  currency: string
  billing_interval: string
  max_reviews_per_month: number
  max_seats: number
}

export type SubscriptionProviderName = 'stripe' | 'mobile_money' | 'bank_transfer' | 'manual'

export interface Subscription {
  id: string
  plan: Plan
  provider: SubscriptionProviderName
  status: 'trialing' | 'active' | 'past_due' | 'canceled' | 'incomplete'
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  is_trial: boolean
  reviews_used: number
  reviews_limit: number
  /** Formule demandée lors d'un paiement, appliquée une fois le paiement confirmé. */
  pending_plan_code: string | null
  /** Accès au service selon le serveur (fin de période + délai de grâce compris). */
  has_access: boolean
  /** Date de coupure de l'accès (fin de période + grâce ; fin exacte pour un essai). */
  access_until: string | null
  seats_used: number
  seats_limit: number
}

export interface Invoice {
  id: string
  /** Numéro séquentiel, ex. RDP-2026-0001. */
  number: string | null
  provider: SubscriptionProviderName
  plan_name: string | null
  months: number
  /** Montant TTC. */
  amount: string
  amount_ht: string | null
  vat_rate: string | null
  vat_amount: string | null
  currency: string
  status: 'pending' | 'pending_review' | 'paid' | 'failed' | 'refunded'
  period_start: string
  period_end: string
  paid_at: string | null
  created_at: string
}

/** Identité légale de l'entreprise, reportée sur ses factures. */
export interface BillingProfile {
  legal_name: string
  address: string
  niu: string
  rccm: string
  email: string
  phone: string
  updated_at: string | null
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface ApiErrorBody {
  detail?: string
  errors?: unknown
  /** Code machine de certaines erreurs (ex : `organization_access_lost`). */
  code?: string
}

/* --- Comptes et équipe ------------------------------------------------------------- */

/** Une organisation de l'utilisateur connecté (sélecteur d'organisation). */
export interface UserOrganization {
  id: string
  name: string
  slug: string
  my_role: MembershipRole
}

/** Places de la formule : membres + invitations en attente, sur `limit` (null = sans abonnement). */
export interface SeatUsage {
  members: number
  pending_invitations: number
  used: number
  limit: number | null
  available: number | null
}

export interface PasswordResetLink {
  reset_url: string
  expires_at: string
}

export interface RegisterResponse {
  access: string
  user: User
  organization: Organization
  trial_granted: boolean
  /** Message à afficher si l'essai gratuit n'a pas été accordé (numéro déjà utilisé…). */
  trial_notice: string | null
}
