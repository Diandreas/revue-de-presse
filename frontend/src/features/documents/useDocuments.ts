import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../../api/client'
import type { Paginated, SourceDocument } from '../../api/types'

export function usePendingDocuments() {
  return useQuery({
    queryKey: ['documents', 'pending'],
    queryFn: async () => {
      const res = await apiClient.get<Paginated<SourceDocument>>('/documents/')
      return res.data.results
    },
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const res = await apiClient.post<SourceDocument>('/documents/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return res.data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents', 'pending'] })
    },
  })
}
