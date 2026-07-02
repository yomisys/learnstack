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

  const logout = () => {
    localStorage.removeItem('token')
    setUser(null)
  }

  const canAuthor = user && ['superadmin', 'admin', 'instructor'].includes(user.role)

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, canAuthor }}>
      {children}
    </AuthContext.Provider>
  )
}
