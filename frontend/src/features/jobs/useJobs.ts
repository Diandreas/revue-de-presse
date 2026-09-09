import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../../api/client'
import type { GeneratedReview, Highlight, Paginated, PressReviewJobDetail, PressReviewJobListItem } from '../../api/types'

const ACTIVE_STATUSES = new Set([
  'UPLOADED',
  'TEXT_EXTRACTION',
  'CHUNKING_SUMMARIZATION',
  'HIGHLIGHT_DETECTION',
  'REVIEW_DRAFTING',
])

export function useJobs() {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: async () => {
      const res = await apiClient.get<Paginated<PressReviewJobListItem>>('/jobs/')
      return res.data.results
    },
    refetchInterval: 8000,
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
    refetchInterval: (query) => (query.state.data && ACTIVE_STATUSES.has(query.state.data.status) ? 3000 : false),
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
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
      void queryClient.invalidateQueries({ queryKey: ['documents', 'pending'] })
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
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs', jobId] })
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
