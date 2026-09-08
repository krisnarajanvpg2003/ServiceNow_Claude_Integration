import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// The React app never talks to ServiceNow directly and never holds ServiceNow
// credentials. It only calls the local MCP HTTP API. In development the Vite
// server proxies /api/* to that backend so the browser sees a same-origin URL
// and no CORS configuration is needed on the backend.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.BACKEND_URL || 'http://127.0.0.1:8095'

  // Hostnames Vite will answer for. Needed when the dev/preview server is
  // shared through a tunnel (Cloudflare, ngrok, VS Code / dev tunnels ...).
  // Override with ALLOWED_HOSTS=host1,host2 in .env; "true" disables the check.
  const allowedHosts =
    env.ALLOWED_HOSTS === 'true'
      ? true
      : env.ALLOWED_HOSTS
        ? env.ALLOWED_HOSTS.split(',').map((h) => h.trim()).filter(Boolean)
        : ['.trycloudflare.com', '.devtunnels.ms', '.ngrok-free.app', '.ngrok.io', '.ngrok.app', '.loca.lt']

  const proxy = {
    '/api': {
      target: backend,
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
  }

  return {
    plugins: [react()],
    server: { port: 5173, proxy, allowedHosts },
    preview: { port: 4173, proxy, allowedHosts },
  }
})
