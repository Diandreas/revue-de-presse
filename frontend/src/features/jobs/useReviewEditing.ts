import { useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { apiClient } from '../../api/client'
import type {
  DetectionCategory,
  GeneratedReview,
  Highlight,
  JobStatus,
  Paginated,
  PressReviewJobDetail,
  PressReviewJobListItem,
  ReviewUpdateInput,
  StructuredReview,
} from '../../api/types'
import { isAdminRole, useAuth } from '../../auth/useAuth'

export interface JobSummary {
  id: string
  title: string
  status: JobStatus
  created_by: string | null
}

const DELETABLE_STATUSES = new Set<JobStatus>(['REVIEW_READY', 'EXPORTED', 'FAILED'])

/** Pourquoi la revue ne peut pas être supprimée par cet utilisateur (null = il peut) —
 * mêmes règles que le serveur : revue terminée ou en échec ; auteur, owner ou admin. */
export function useDeleteDenial(job: JobSummary): string | null {
  const { user, organization } = useAuth()
  if (!DELETABLE_STATUSES.has(job.status)) return 'Analyse en cours : attendez la fin pour supprimer.'
  if (isAdminRole(organization?.my_role) || (user && job.created_by === user.id)) return null
  return 'Réservé à l’auteur de la revue ou à un administrateur.'
}

/* Relecture de la revue : corrections, points clés masqués, renommage, suppression.
 * Les corrections s'affichent tout de suite (mise à jour optimiste du cache) ; en cas
 * d'échec, l'état précédent est rétabli et l'appelant affiche l'erreur. */

const reviewKey = (jobId: string) => ['jobs', jobId, 'review']
const highlightsKey = (jobId: string) => ['jobs', jobId, 'highlights']

function setJobTitle(queryClient: QueryClient, jobId: string, title: string) {
  queryClient.setQueryData<PressReviewJobDetail>(['jobs', jobId], (job) => (job ? { ...job, title } : job))
}

interface UpdateReviewVariables {
  changes: ReviewUpdateInput
  /** Revue telle qu'elle s'affichera une fois enregistrée (affichage immédiat). */
  optimistic: StructuredReview
}

export function useUpdateReview(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ changes }: UpdateReviewVariables) => {
      const res = await apiClient.patch<GeneratedReview>(`/jobs/${jobId}/review/`, changes)
      return res.data
    },
    onMutate: async ({ changes, optimistic }) => {
      await queryClient.cancelQueries({ queryKey: reviewKey(jobId) })
      const previousReview = queryClient.getQueryData<GeneratedReview>(reviewKey(jobId))
      const previousJob = queryClient.getQueryData<PressReviewJobDetail>(['jobs', jobId])
      if (previousReview) {
        queryClient.setQueryData<GeneratedReview>(reviewKey(jobId), {
          ...previousReview,
          structured: optimistic,
          is_edited: previousReview.is_edited || Boolean(changes.sections || changes.date_label !== undefined),
          pdf_file: null,
          docx_file: null,
        })
      }
      if (changes.title) setJobTitle(queryClient, jobId, changes.title)
      return { previousReview, previousJob }
    },
    onError: (_error, _variables, context) => {
      if (context?.previousReview) queryClient.setQueryData(reviewKey(jobId), context.previousReview)
      if (context?.previousJob) queryClient.setQueryData(['jobs', jobId], context.previousJob)
    },
    onSuccess: (review) => queryClient.setQueryData(reviewKey(jobId), review),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs', jobId], exact: true })
      void queryClient.invalidateQueries({ queryKey: ['jobs', 'list'] })
    },
  })
}

export function useRestoreReview(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<GeneratedReview>(`/jobs/${jobId}/review/restore/`)
      return res.data
    },
    onSuccess: (review) => queryClient.setQueryData(reviewKey(jobId), review),
  })
}

interface UpdateHighlightVariables {
  highlightId: string
  hidden?: boolean
  category?: DetectionCategory
}

export function useUpdateHighlight(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ highlightId, hidden, category }: UpdateHighlightVariables) => {
      const body: { hidden?: boolean; category?: string } = {}
      if (hidden !== undefined) body.hidden = hidden
      if (category) body.category = category.id
      const res = await apiClient.patch<Highlight>(`/jobs/${jobId}/highlights/${highlightId}/`, body)
      return res.data
    },
    onMutate: async ({ highlightId, hidden, category }) => {
      await queryClient.cancelQueries({ queryKey: highlightsKey(jobId) })
      const previous = queryClient.getQueryData<Highlight[]>(highlightsKey(jobId))
      queryClient.setQueryData<Highlight[]>(highlightsKey(jobId), (items) =>
        items?.map((item) =>
          item.id === highlightId
            ? { ...item, ...(hidden !== undefined && { hidden }), ...(category && { category }) }
            : item,
        ),
      )
      return { previous }
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(highlightsKey(jobId), context.previous)
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: highlightsKey(jobId) })
      // L'annexe des exports a changé (cache vidé côté serveur) et les compteurs aussi.
      void queryClient.invalidateQueries({ queryKey: reviewKey(jobId) })
      void queryClient.invalidateQueries({ queryKey: ['jobs', 'list'] })
      void queryClient.invalidateQueries({ queryKey: ['jobs', 'stats'] })
    },
  })
}

export function useRenameJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ jobId, title }: { jobId: string; title: string }) => {
      const res = await apiClient.patch<PressReviewJobDetail>(`/jobs/${jobId}/`, { title })
      return res.data
    },
    onSuccess: (job) => {
      setJobTitle(queryClient, job.id, job.title)
      queryClient.setQueriesData<Paginated<PressReviewJobListItem>>({ queryKey: ['jobs', 'list'] }, (page) =>
        page ? { ...page, results: page.results.map((item) => (item.id === job.id ? { ...item, title: job.title } : item)) } : page,
      )
      void queryClient.invalidateQueries({ queryKey: reviewKey(job.id) }) // exports périmés
    },
  })
}

export function useDeleteJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (jobId: string) => {
      await apiClient.delete(`/jobs/${jobId}/`)
      return jobId
    },
    onSuccess: (jobId) => {
      queryClient.setQueriesData<Paginated<PressReviewJobListItem>>({ queryKey: ['jobs', 'list'] }, (page) =>
        page ? { ...page, count: Math.max(0, page.count - 1), results: page.results.filter((item) => item.id !== jobId) } : page,
      )
      queryClient.removeQueries({ queryKey: ['jobs', jobId] })
      void queryClient.invalidateQueries({ queryKey: ['jobs', 'list'] })
      void queryClient.invalidateQueries({ queryKey: ['jobs', 'stats'] })
    },
  })
}
