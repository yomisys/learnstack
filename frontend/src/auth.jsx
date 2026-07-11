import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!localStorage.getItem('token'))

  useEffect(() => {
    if (!localStorage.getItem('token')) return
    api
      .get('/api/auth/me')
      .then((r) => setUser(r.data))
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setLoading(false))
  }, [])

  const handleToken = (data) => {
    localStorage.setItem('token', data.access_token)
    setUser(data.user)
  }

  const login = async (email, password) => {
    const r = await api.post('/api/auth/login', { email, password })
    handleToken(r.data)
  }

  const register = async (email, password, full_name) => {
    const r = await api.post('/api/auth/register', { email, password, full_name })
    handleToken(r.data)
  }

  // Org signup returns a token like login/register, but for a brand-new
  // tenant — the caller is responsible for switching TENANT (api.js reads
  // it from localStorage at module load, so this needs a hard navigation,
  // not just handleToken + client-side route change).
  const signupOrg = async (body) => {
    const r = await api.post('/api/tenants/signup', body)
    localStorage.setItem('token', r.data.access_token)
    return r.data
  }

  const logout = () => {
    localStorage.removeItem('token')
    setUser(null)
  }

  const canAuthor = user && ['superadmin', 'admin', 'instructor'].includes(user.role)
  // Matches the backend's require_roles(SUPERADMIN, ADMIN) gate on
  // /api/analytics/* — narrower than canAuthor because analytics exposes
  // learner names/emails, which instructors don't otherwise see.
  const canManageTenant = user && ['superadmin', 'admin'].includes(user.role)

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, signupOrg, logout, canAuthor, canManageTenant }}>
      {children}
    </AuthContext.Provider>
  )
}
