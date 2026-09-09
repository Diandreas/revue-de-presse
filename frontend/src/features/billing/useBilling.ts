import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { apiClient } from '../../api/client'
import type { Invoice, Paginated, Plan, Subscription } from '../../api/types'

export function usePlans() {
  return useQuery({
    queryKey: ['plans'],
    queryFn: async () => {
      const res = await apiClient.get<Paginated<Plan>>('/billing/plans/')
      return res.data.results
    },
  })
}

export function useSubscription() {
  return useQuery({
    queryKey: ['subscription'],
    queryFn: async () => {
      try {
        const res = await apiClient.get<Subscription>('/billing/subscription/')
        return res.data
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 404) return null
        throw error
      }
    },
  })
}

export function useInvoices() {
  return useQuery({
    queryKey: ['invoices'],
    queryFn: async () => {
      const res = await apiClient.get<Paginated<Invoice>>('/billing/invoices/')
      return res.data.results
    },
  })
}

export interface CheckoutResult {
  provider: string
  mock?: boolean
  checkout_url?: string | null
  reference?: string | null
  invoice_id?: string
  detail?: string
}

export function useCheckoutStripe() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (planCode: string) => {
      const res = await apiClient.post<CheckoutResult>('/billing/checkout/stripe/', { plan_code: planCode })
      return res.data
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['subscription'] }),
  })
}

export function useCheckoutMobileMoney() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: { planCode: string; phoneNumber: string }) => {
      const res = await apiClient.post<CheckoutResult>('/billing/checkout/mobile-money/', {
        plan_code: input.planCode,
        phone_number: input.phoneNumber,
      })
      return res.data
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['subscription'] }),
  })
}

export function useCheckoutBankTransfer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (planCode: string) => {
      const res = await apiClient.post<CheckoutResult>('/billing/checkout/bank-transfer/', { plan_code: planCode })
      return res.data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['subscription'] })
      void queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
  })
}

export function useUploadInvoiceProof() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ invoiceId, file }: { invoiceId: string; file: File }) => {
      const formData = new FormData()
      formData.append('proof', file)
      const res = await apiClient.post<Invoice>(`/billing/invoices/${invoiceId}/proof/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return res.data
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['invoices'] }),
  })
}

export function useCancelSubscription() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<Subscription>('/billing/subscription/cancel/')
      return res.data
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['subscription'] }),
  })
}
