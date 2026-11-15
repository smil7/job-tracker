import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { CALLBACK_PATH, authDisabled, completeLogin, getUser, login, logout } from './auth'
import { SessionContext } from './session'

type State =
  | { kind: 'loading' }
  | { kind: 'ready'; email: string | null }
  | { kind: 'error'; message: string }

// Only one start-up may run. React StrictMode runs effects twice in development, and a login
// code can be traded only once.
let starting: Promise<State> | undefined

function start(): Promise<State> {
  starting ??= (async (): Promise<State> => {
    if (authDisabled) return { kind: 'ready', email: null }
    try {
      if (window.location.pathname === CALLBACK_PATH) {
        await completeLogin()
        window.history.replaceState(null, '', '/') // remove ?code=... from the address bar
      }
      const user = await getUser()
      if (!user) {
        await login() // leaves this page
        return { kind: 'loading' }
      }
      return { kind: 'ready', email: (user.profile.email as string | undefined) ?? null }
    } catch (error) {
      return { kind: 'error', message: error instanceof Error ? error.message : 'Login failed' }
    }
  })()
  return starting
}

/** Shows the app only after login worked. Otherwise it sends the user to the login page. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let active = true
    void start().then((s) => active && setState(s))
    return () => {
      active = false
    }
  }, [])

  if (state.kind === 'loading') {
    return <p className="p-6 text-sm text-stone-500">Signing in…</p>
  }
  if (state.kind === 'error') {
    return (
      <div className="mx-auto mt-24 max-w-sm text-center">
        <p className="text-lg font-medium">Couldn't sign you in</p>
        <p className="mt-1 text-sm text-stone-500">{state.message}</p>
        <button
          onClick={() => {
            starting = undefined
            window.history.replaceState(null, '', '/')
            void login()
          }}
          className="mt-4 rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700"
        >
          Try again
        </button>
      </div>
    )
  }
  return (
    <SessionContext.Provider value={{ email: state.email, logout: () => void logout() }}>
      {children}
    </SessionContext.Provider>
  )
}
