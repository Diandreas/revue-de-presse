export interface User {
  id: string
  email: string
  full_name: string
  date_joined: string
}

export interface Organization {
  id: string
  name: string
  slug: string
  country: string
  default_locale: string
  created_at: string
}

export type MembershipRole = 'owner' | 'admin' | 'member'

export interface Membership {
  id: string
  user: User
  role: MembershipRole
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

export interface SourceDocument {
  id: string
  file: string
  original_filename: string
  page_count: number | null
  requires_ocr: boolean | null
  extraction_status: ExtractionStatus
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

export interface PressReviewJobListItem {
  id: string
  title: string
  status: JobStatus
  progress_percent: number
  created_at: string
  completed_at: string | null
}

export interface PressReviewJobDetail extends PressReviewJobListItem {
  error_message: string
  started_at: string | null
  step_runs: PipelineStepRun[]
  documents: SourceDocument[]
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
}

export interface GeneratedReview {
  summary_markdown: string
  pdf_file: string | null
  docx_file: string | null
  generated_at: string | null
}

export interface Plan {
  id: string
  code: string
  name: string
  price_amount: string
  currency: string
  billing_interval: string
  max_reviews_per_month: number
  max_seats: number
}

export type SubscriptionProviderName = 'stripe' | 'mobile_money' | 'bank_transfer'

export interface Subscription {
  id: string
  plan: Plan
  provider: SubscriptionProviderName
  status: 'trialing' | 'active' | 'past_due' | 'canceled' | 'incomplete'
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
}

export interface Invoice {
  id: string
  provider: SubscriptionProviderName
  amount: string
  currency: string
  status: 'pending' | 'pending_review' | 'paid' | 'failed' | 'refunded'
  period_start: string
  period_end: string
  paid_at: string | null
  proof_file: string | null
  created_at: string
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
}
