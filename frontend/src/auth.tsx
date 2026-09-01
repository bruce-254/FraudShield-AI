import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, login as apiLogin } from './api'
import type { User } from './types'

interface AuthCtx {
  user: User | null
  loading: boolean
  signIn: (u: string, p: string) => Promise<void>
  signOut: () => void
}

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('fs_token')
    if (!token) { setLoading(false); return }
    api.get('/auth/me')
      .then((r) => setUser(r.data))
      .catch(() => localStorage.removeItem('fs_token'))
      .finally(() => setLoading(false))
  }, [])

  const signIn = async (username: string, password: string) => {
    const token = await apiLogin(username, password)
    localStorage.setItem('fs_token', token)
    const { data } = await api.get('/auth/me')
    setUser(data)
  }

  const signOut = () => {
    localStorage.removeItem('fs_token')
    setUser(null)
  }

  return <Ctx.Provider value={{ user, loading, signIn, signOut }}>{children}</Ctx.Provider>
}
