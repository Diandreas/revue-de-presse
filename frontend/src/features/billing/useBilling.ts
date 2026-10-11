import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { apiClient } from '../../api/client'
import type { BillingProfile, Invoice, Paginated, Plan, Subscription } from '../../api/types'

/* Facturation en mode manuel : aucun paiement en ligne. Le client contacte l'équipe
 * (WhatsApp) qui active / prolonge l'abonnement depuis l'administration. */

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

/** Télécharge le PDF d'une facture (requête authentifiée, puis enregistrement local). */
export function useDownloadInvoicePdf() {
  return useMutation({
    mutationFn: async (invoice: Invoice) => {
      let res
      try {
        res = await apiClient.get<Blob>(`/billing/invoices/${invoice.id}/pdf/`, { responseType: 'blob' })
      } catch (error) {
        // En mode blob, le message d'erreur JSON du serveur arrive lui aussi en Blob : on le
        // relit pour que extractErrorMessage affiche le vrai motif.
        if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
          try {
            error.response.data = JSON.parse(await error.response.data.text())
          } catch {
            // corps non JSON : message générique
          }
        }
        throw error
      }
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = `${invoice.number ?? 'facture'}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    },
  })
}

export function useBillingProfile() {
  return useQuery({
    queryKey: ['billing-profile'],
    queryFn: async () => {
      const res = await apiClient.get<BillingProfile>('/billing/profile/')
      return res.data
    },
  })
}

export function useUpdateBillingProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (profile: Omit<BillingProfile, 'updated_at'>) => {
      const res = await apiClient.put<BillingProfile>('/billing/profile/', profile)
      return res.data
    },
    onSuccess: (data) => queryClient.setQueryData(['billing-profile'], data),
  })
}

export function useCancelSubscription() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<Subscription>('/billing/subscription/cancel/')
      return res.data
    },
    onSuccess: (data) => queryClient.setQueryData(['subscription'], data),
  })
}

export function useResumeSubscription() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<Subscription>('/billing/subscription/resume/')
      return res.data
    },
    onSuccess: (data) => queryClient.setQueryData(['subscription'], data),
  })
}
