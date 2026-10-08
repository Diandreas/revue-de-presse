import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../../api/client'
import type {
  GeneratedReview,
  Highlight,
  JobStats,
  JobStatus,
  Paginated,
  PressReviewJobDetail,
  PressReviewJobListItem,
} from '../../api/types'

export const ACTIVE_STATUSES = new Set<JobStatus>([
  'UPLOADED',
  'TEXT_EXTRACTION',
  'CHUNKING_SUMMARIZATION',
  'HIGHLIGHT_DETECTION',
  'REVIEW_DRAFTING',
])
export const READY_STATUSES = new Set<JobStatus>(['REVIEW_READY', 'EXPORTED'])

export function useJobs(pageSize = 20) {
  return useQuery({
    queryKey: ['jobs', 'list', pageSize],
    queryFn: async () => {
      const res = await apiClient.get<Paginated<PressReviewJobListItem>>('/jobs/', { params: { page_size: pageSize } })
      return res.data
    },
    placeholderData: (previous) => previous,
    // Revue en cours : on suit sa progression de près ; sinon, un rafraîchissement lent suffit.
    refetchInterval: (query) =>
      query.state.data?.results.some((job) => ACTIVE_STATUSES.has(job.status)) ? 4000 : 20000,
    // L'analyse continue en arrière-plan pendant que l'utilisateur est ailleurs : au retour
    // sur l'onglet, on rafraîchit tout de suite (le polling est en pause onglet masqué).
    refetchOnWindowFocus: true,
  })
}

export function useJobStats() {
  return useQuery({
    queryKey: ['jobs', 'stats'],
    queryFn: async () => {
      const res = await apiClient.get<JobStats>('/jobs/stats/')
      return res.data
    },
    refetchInterval: (query) => (query.state.data?.active ? 5000 : 30000),
    refetchOnWindowFocus: true,
  })
}

export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: ['jobs', jobId],
    queryFn: async () => {
      const res = await apiClient.get<PressReviewJobDetail>(`/jobs/${jobId}/`)
      return res.data
    },
    enabled: Boolean(jobId),
    refetchInterval: (query) => (query.state.data && ACTIVE_STATUSES.has(query.state.data.status) ? 2500 : false),
    refetchOnWindowFocus: true, // cf. useJobs : retour sur l'onglet = état à jour immédiatement
  })
}

export function useCreateJob() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: async (input: { title: string; document_ids: string[] }) => {
      const res = await apiClient.post<PressReviewJobDetail>('/jobs/', input)
      return res.data
    },
    onSuccess: (job) => {
      queryClient.setQueryData(['jobs', job.id], job)
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
      void queryClient.invalidateQueries({ queryKey: ['documents', 'pending'] })
      void queryClient.invalidateQueries({ queryKey: ['subscription'] })
      navigate(`/jobs/${job.id}`)
    },
  })
}

export function useRetryJob(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<PressReviewJobDetail>(`/jobs/${jobId}/retry/`)
      return res.data
    },
    onSuccess: (job) => {
      queryClient.setQueryData(['jobs', jobId], job)
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
}

export function useJobHighlights(jobId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['jobs', jobId, 'highlights'],
    queryFn: async () => {
      const res = await apiClient.get<Highlight[]>(`/jobs/${jobId}/highlights/`)
      return res.data
    },
    enabled: Boolean(jobId) && enabled,
  })
}

export function useJobReview(jobId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['jobs', jobId, 'review'],
    queryFn: async () => {
      const res = await apiClient.get<GeneratedReview>(`/jobs/${jobId}/review/`)
      return res.data
    },
    enabled: Boolean(jobId) && enabled,
  })
}

export function useExportReview(jobId: string) {
  return useMutation({
    mutationFn: async (format: 'pdf' | 'docx') => {
      // NB: le paramètre s'appelle export_format, pas format — DRF réserve `format`
      // pour sa propre négociation de contenu (voir apps/press_review/views.py).
      const res = await apiClient.get<{ url: string }>(`/jobs/${jobId}/review/export/`, {
        params: { export_format: format },
      })
      return res.data.url
    },
  })
}
