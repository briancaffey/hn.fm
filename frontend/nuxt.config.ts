import tailwindcss from '@tailwindcss/vite'
import tsconfigPaths from 'vite-tsconfig-paths'
import { fileURLToPath } from 'node:url'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  // Node resolves the default host `localhost` to ::1 on macOS, so the dev
  // server would listen on [::1]:3000 only — 127.0.0.1:3000 refused the
  // connection and Chrome showed an error page. Bind both stacks.
  devServer: { host: '0.0.0.0', port: 3000 },

  nitro: {
    devProxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // SSE (/api/activity/stream) is proxied too; without disabling the
        // proxy's response buffering, events arrive in bursts long after the
        // work happened, which defeats the point of a live view.
        selfHandleResponse: false,
        buffer: false
      }
    }
  },

  icon: {
    // @nuxt/icon serves its bundled icon sets from `/api/_nuxt_icon` by
    // default, and the devProxy above forwards everything under `/api` to
    // FastAPI — which answers `{"detail":"Not found"}`. Every icon on every
    // page was therefore falling through to the public Iconify CDN, so the
    // UI made an external request per icon and a request that failed left a
    // button rendered as an empty box. Moved off `/api` so the local set is
    // actually used.
    localApiEndpoint: '/_icons',
  },

  css: ['~/assets/css/tailwind.css'],

  vite: {
    plugins: [
      tailwindcss(),
      tsconfigPaths()
    ],

  },

  modules: [
    '@nuxt/fonts',
    '@nuxt/content',
    '@nuxt/image',
    '@nuxt/icon',
    '@nuxt/eslint',
    '@nuxt/scripts',
    '@nuxt/test-utils',
    'shadcn-nuxt',
    '@pinia/nuxt',
    '@nuxtjs/color-mode',
  ],

  shadcn: {
    /**
     * Prefix for all the imported component
     */
    prefix: '',
    /**
     * Directory that the component lives in.
     * @default "./components/ui"
     */
    componentDir: './app/components/ui'
  },

  colorMode: {
    preference: 'system',
    fallback: 'light',
    classPrefix: '',
    classSuffix: '-mode',
    storageKey: 'nuxt-color-mode'
  },

  runtimeConfig: {
    // Server-only: where SSR forwards /api when apiBase is relative
    // (server/api/[...].ts). Env: NUXT_API_UPSTREAM.
    apiUpstream: 'http://localhost:8000',
    public: {
      // Origin the browser calls the API on. Empty = same origin as the page
      // (the cluster ingress); the dev default is the FastAPI dev server.
      // Env: NUXT_PUBLIC_API_BASE.
      apiBase: 'http://localhost:8000',
    }
  },

  testUtils: {
    startTimeout: 15000,
    vitestConfig: {
      resolve: {
        alias: {
          '~': fileURLToPath(new URL('./', import.meta.url)),
          '@': fileURLToPath(new URL('./', import.meta.url)),
        },
      },
    },
  },
})