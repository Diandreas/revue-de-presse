import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../../api/client'
import type { Paginated, SourceDocument } from '../../api/types'

/** Documents téléversés mais pas encore rattachés à une revue. */
export function usePendingDocuments() {
  return useQuery({
    queryKey: ['documents', 'pending'],
    queryFn: async () => {
      const res = await apiClient.get<Paginated<SourceDocument>>('/documents/', { params: { page_size: 100 } })
      return res.data.results
    },
  })
}

export async function uploadDocument(
  file: File,
  { onProgress, signal }: { onProgress?: (percent: number) => void; signal?: AbortSignal } = {},
) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await apiClient.post<SourceDocument>('/documents/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    signal,
    onUploadProgress: (event) => {
      if (onProgress && event.total) onProgress(Math.round((event.loaded / event.total) * 100))
    },
  })
  return res.data
}

export function useDeletePendingDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (documentId: string) => {
      await apiClient.delete(`/documents/${documentId}/`)
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['documents', 'pending'] }),
  })
}
