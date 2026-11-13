import createClient from 'openapi-fetch'
import type { Middleware } from 'openapi-fetch'
import { getAccessToken, login } from '../auth/auth'
import type { paths } from './schema'

// Same origin: Vite proxies /api to the FastAPI server in dev
export const api = createClient<paths>({ baseUrl: '' })

const auth: Middleware = {
  // Add the login token to every request. With login off there is no token and nothing is added.
  async onRequest({ request }) {
    const token = await getAccessToken()
    if (token) request.headers.set('Authorization', `Bearer ${token}`)
    return request
  },
  // 401 means the token is missing or too old: go through the login page again.
  // (503 is different: the login service is down. We do not log the user out for that.)
  async onResponse({ response }) {
    if (response.status === 401) void login()
    return response
  },
}
api.use(auth)

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${result.response.status})`)
  }
  return result.data as T
}
