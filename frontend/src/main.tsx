import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import { AuthProvider } from './auth/AuthContext'
import { ErrorBoundary, RouteErrorBoundary } from './components/ErrorBoundary'
import { ToastProvider } from './components/Toast'
import { installChunkReloadHandler } from './lib/chunkReload'
import './index.css'

// Onglet resté ouvert pendant un déploiement : recharge unique au lieu d'une page blanche.
installChunkReloadHandler()

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <ToastProvider>
              <RouteErrorBoundary>
                <App />
              </RouteErrorBoundary>
            </ToastProvider>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)
