import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Cible du proxy dev vers le backend Django. Surchargeable via VITE_PROXY_TARGET
  // (utile si le port 8000 est déjà pris par un autre projet local). 127.0.0.1 plutôt que
  // localhost : sous Windows, `localhost` tente l'IPv6 d'abord (~2 s de délai par connexion).
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target: proxyTarget, changeOrigin: true },
      },
    },
  }
})
