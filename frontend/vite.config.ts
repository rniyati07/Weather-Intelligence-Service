import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type ProxyOptions } from 'vite'

/**
 * Dev-time BFF proxy.
 *
 * FDS constraint #3: the backend API key must never reach the browser. The
 * browser therefore talks to a same-origin `/api` path, and *this* proxy —
 * which runs in Node, not in the bundle — attaches `X-API-Key`.
 *
 * `API_KEY` is deliberately NOT `VITE_`-prefixed, so Vite refuses to inline it
 * into client code even if someone references it by mistake. In production the
 * same contract is served by a real BFF; client code does not change, because
 * the path it calls stays `/api`.
 */
function createApiProxy(env: Record<string, string>): Record<string, ProxyOptions> {
  const target = env.API_PROXY_TARGET || 'http://localhost:8000'
  const apiKey = env.API_KEY
  const opsApiKey = env.OPS_API_KEY

  return {
    '/api': {
      target,
      changeOrigin: true,
      configure(proxy) {
        proxy.on('proxyReq', (proxyReq, req) => {
          const isOperatorRoute = req.url?.includes('/providers/health') ?? false
          const key = isOperatorRoute ? (opsApiKey ?? apiKey) : apiKey
          if (key) proxyReq.setHeader('X-API-Key', key)
        })
      },
    },
  }
}

export default defineConfig(({ mode }) => {
  // The `''` prefix loads every var, including the non-public ones used above.
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: createApiProxy(env),
    },
    // LOCAL VERIFICATION ONLY — `npm run build && npm run preview`.
    //
    // `vite preview` serves the production bundle but does *not* inherit
    // `server.proxy`, so without this the built app has no `/api` to call and
    // cannot be checked against a real backend before shipping.
    //
    // This is not a deployment target. `vite preview` is a development server
    // and must never front production traffic; there, the same
    // inject-the-key-server-side role belongs to the deployed BFF. The key is
    // read here in Node config and never enters the client graph — verified by
    // grepping `dist/` for it as part of the build check.
    preview: {
      port: 4173,
      proxy: createApiProxy(env),
    },
    build: {
      target: 'es2022',
      sourcemap: mode !== 'production',
      rollupOptions: {
        output: {
          // Keep the vendor half of the graph out of the app chunk so a UI
          // change does not invalidate unchanged library code.
          manualChunks(id) {
            if (!id.includes('node_modules')) return

            if (/[\\/]node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/.test(id)) {
              return 'react'
            }
            if (/[\\/]node_modules[\\/](@tanstack|axios)[\\/]/.test(id)) return 'query'
            if (/[\\/]node_modules[\\/](framer-motion|motion-dom|motion-utils)[\\/]/.test(id)) {
              return 'motion'
            }
            return
          },
        },
      },
    },
  }
})
