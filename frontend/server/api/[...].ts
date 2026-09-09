// Same-origin API for server-side rendering.
//
// In the cluster the browser reaches FastAPI at /api on whatever hostname it
// loaded the page from (the ingress path-routes /api past this server), so
// NUXT_PUBLIC_API_BASE is empty and every URL the app builds is relative —
// which is what lets one deployment answer to hnfm.lan AND the tailnet name.
//
// The one place a relative /api URL can't work is SSR: `$fetch('/api/…')` on
// the server dispatches to Nitro itself, not to the ingress. This catch-all
// takes those and forwards them to the backend over the cluster network
// (NUXT_API_UPSTREAM, e.g. http://hnfm-web:8000). In `nuxt dev` the devProxy
// in nuxt.config.ts answers /api first, so this handler is never reached.
export default defineEventHandler((event) => {
  const upstream = useRuntimeConfig(event).apiUpstream.replace(/\/$/, '')
  return proxyRequest(event, `${upstream}${event.path}`)
})
