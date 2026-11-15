// Login with Amazon Cognito: authorization code flow with PKCE.
//
// The browser never sees a password. It goes to the Cognito login page, comes back with a
// one-time code, and trades the code for tokens. PKCE makes a stolen code useless.
import { UserManager, WebStorageStateStore } from 'oidc-client-ts'
import type { User } from 'oidc-client-ts'

// Local development skips login. Only `.env.development` sets this, and Vite reads that file
// only for `npm run dev`. A production build has login on, even if the variable is missing.
export const authDisabled = import.meta.env.VITE_AUTH_DISABLED === 'true'

const region = import.meta.env.VITE_COGNITO_REGION as string | undefined
const poolId = import.meta.env.VITE_COGNITO_USER_POOL_ID as string | undefined
const clientId = import.meta.env.VITE_COGNITO_APP_CLIENT_ID as string | undefined
// Hosted UI domain, for example myapp.auth.eu-central-1.amazoncognito.com
const domain = import.meta.env.VITE_COGNITO_DOMAIN as string | undefined

export const CALLBACK_PATH = '/auth/callback'

function createManager(): UserManager | null {
  if (authDisabled) return null
  if (!region || !poolId || !clientId || !domain) {
    throw new Error(
      'Login is not set up. Set VITE_COGNITO_REGION, VITE_COGNITO_USER_POOL_ID, ' +
        'VITE_COGNITO_APP_CLIENT_ID and VITE_COGNITO_DOMAIN, or VITE_AUTH_DISABLED=true for local development.',
    )
  }
  return new UserManager({
    // oidc-client-ts reads <authority>/.well-known/openid-configuration. Cognito serves it there.
    authority: `https://cognito-idp.${region}.amazonaws.com/${poolId}`,
    client_id: clientId,
    redirect_uri: `${window.location.origin}${CALLBACK_PATH}`,
    response_type: 'code',
    scope: 'openid email',
    // Tokens live in sessionStorage (the default): they are gone when the tab closes.
    // The Cognito login page remembers you, so a new tab signs in again without a password.
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    // Get a new access token with the refresh token before the old one ends
    automaticSilentRenew: true,
  })
}

let manager: UserManager | null | undefined
function getManager(): UserManager | null {
  if (manager === undefined) manager = createManager()
  return manager
}

/** The access token for the API, or null if nobody is logged in (or login is off). */
export async function getAccessToken(): Promise<string | null> {
  const user = await getManager()?.getUser()
  return user && !user.expired ? user.access_token : null
}

export async function getUser(): Promise<User | null> {
  const user = await getManager()?.getUser()
  return user && !user.expired ? user : null
}

let redirecting = false
/** Go to the Cognito login page. */
export async function login(): Promise<void> {
  if (redirecting) return
  redirecting = true
  await getManager()?.signinRedirect()
}

/** Finish the login after Cognito sends the browser back with ?code=... */
export async function completeLogin(): Promise<void> {
  await getManager()?.signinCallback()
}

/** Forget the tokens here, and end the Cognito session too. */
export async function logout(): Promise<void> {
  const m = getManager()
  if (!m) return
  await m.removeUser()
  // Cognito has its own /logout address (it has no standard end_session endpoint)
  const url = new URL(`https://${domain}/logout`)
  url.searchParams.set('client_id', clientId!)
  url.searchParams.set('logout_uri', window.location.origin)
  window.location.assign(url.toString())
}
