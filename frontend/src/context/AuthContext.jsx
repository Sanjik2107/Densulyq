import { createContext, useContext, useState, useEffect } from 'react'
import { AUTH_STORAGE_KEY } from '../utils.jsx'
import { apiGet, apiPost } from '../api.js'

const AuthContext = createContext(null)

function getStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return {
      token: typeof parsed.token === 'string' ? parsed.token : '',
      portal: typeof parsed.portal === 'string' ? parsed.portal : 'patient',
      page: typeof parsed.page === 'string' ? parsed.page : '',
    }
  } catch { return { token: '', portal: 'patient', page: '' } }
}

function setStoredAuth(state) {
  try { localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(state)) } catch {}
}

function clearStoredAuth() {
  try { localStorage.removeItem(AUTH_STORAGE_KEY) } catch {}
}

export function AuthProvider({ children }) {
  const [authState, setAuthState] = useState(getStoredAuth)
  const [context, setContext] = useState({ user: null, permissions: [], portal: 'patient' })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!authState.token) { setLoading(false); return }
    apiGet('/auth/me')
      .then(data => setContext(data))
      .catch(() => { clearStoredAuth(); setAuthState({ token: '', portal: 'patient', page: '' }) })
      .finally(() => setLoading(false))
  }, [])

  const login = async (username, password) => {
    const data = await apiPost('/auth/login', { username, password }, true)
    const newState = { token: data.token, portal: data.portal, page: data.user?.role === 'admin' ? 'admin' : 'dashboard' }
    setStoredAuth(newState)
    setAuthState(newState)
    setContext({ user: data.user, permissions: data.permissions || [], portal: data.portal })
    return data
  }

  const register = async (payload) => {
    const data = await apiPost('/auth/register', payload, true)
    const newState = { token: data.token, portal: data.portal, page: 'dashboard' }
    setStoredAuth(newState)
    setAuthState(newState)
    setContext({ user: data.user, permissions: data.permissions || [], portal: data.portal })
    return data
  }

  const logout = async () => {
    try { if (authState.token) await apiPost('/auth/logout') } catch {}
    clearStoredAuth()
    setAuthState({ token: '', portal: 'patient', page: '' })
    setContext({ user: null, permissions: [], portal: 'patient' })
  }

  const updateStoredPage = (page) => {
    const next = { ...authState, page }
    setStoredAuth(next)
    setAuthState(next)
  }

  return (
    <AuthContext.Provider value={{
      authState, context, loading,
      user: context.user, permissions: context.permissions,
      isAdmin: context.user?.role === 'admin',
      isDoctor: context.user?.role === 'doctor',
      isPatient: context.user?.role === 'user',
      isAuthenticated: !!authState.token,
      login, register, logout, updateStoredPage,
      setContext,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
