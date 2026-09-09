import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../../api/client'
import type { DetectionCategory, Paginated } from '../../api/types'

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const res = await apiClient.get<Paginated<DetectionCategory>>('/detection-categories/')
      return res.data.results
    },
  })
}

export type CategoryInput = Pick<
  DetectionCategory,
  'name' | 'type' | 'description' | 'prompt_hint' | 'color' | 'is_active' | 'sort_order' | 'keywords'
>

export function useCreateCategory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: CategoryInput) => {
      const res = await apiClient.post<DetectionCategory>('/detection-categories/', input)
      return res.data
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['categories'] }),
  })
}

export function useUpdateCategory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...input }: Partial<CategoryInput> & { id: string }) => {
      const res = await apiClient.patch<DetectionCategory>(`/detection-categories/${id}/`, input)
      return res.data
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['categories'] }),
  })
}

export function useDeleteCategory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/detection-categories/${id}/`)
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['categories'] }),
  })
}
