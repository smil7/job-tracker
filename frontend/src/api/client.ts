import createClient from 'openapi-fetch'
import type { paths } from './schema'

// Same origin: Vite proxies /api to the FastAPI server in dev
export const api = createClient<paths>({ baseUrl: '' })

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${result.response.status})`)
  }
  return result.data as T
}
