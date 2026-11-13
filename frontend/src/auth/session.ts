import { createContext, useContext } from 'react'

export type Session = { email: string | null; logout: () => void }

export const SessionContext = createContext<Session>({ email: null, logout: () => {} })

/** Who is logged in, and how to log out. In local development with login off, email is null. */
export function useSession(): Session {
  return useContext(SessionContext)
}
