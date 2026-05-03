import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { AUTH_STORAGE_KEY } from '../utils.jsx'
import { apiGet, apiPost, setUnauthorizedHandler } from '../api.js'

const AuthContext = createContext(null)

function getStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return {
      token: typeof parsed.token === 'string' ? parsed.token : '',
      csrfToken: typeof parsed.csrfToken === 'string' ? parsed.csrfToken : '',
      session: parsed.session === true,
      portal: typeof parsed.portal === 'string' ? parsed.portal : 'patient',
      page: typeof parsed.page === 'string' ? parsed.page : '',
    }
  } catch { return { token: '', csrfToken: '', session: false, portal: 'patient', page: '' } }
}

function setStoredAuth(state) {
  try { localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(state)) } catch { return }
}

function clearStoredAuth() {
  try { localStorage.removeItem(AUTH_STORAGE_KEY) } catch { return }
}

export function AuthProvider({ children }) {
  const [authState, setAuthState] = useState(getStoredAuth)
  const [context, setContext] = useState({ user: null, permissions: [], portal: 'patient' })
  const [loading, setLoading] = useState(true)

  const clearAuthState = useCallback(() => {
    clearStoredAuth()
    setAuthState({ token: '', csrfToken: '', session: false, portal: 'patient', page: '' })
    setContext({ user: null, permissions: [], portal: 'patient' })
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => clearAuthState())
    return () => setUnauthorizedHandler(null)
  }, [clearAuthState])

  useEffect(() => {
    if (!authState.token && !authState.session) { setLoading(false); return }
    apiGet('/auth/me')
      .then(data => setContext(data))
      .catch(() => clearAuthState())
      .finally(() => setLoading(false))
  }, [authState.session, authState.token, clearAuthState])

  const login = async (username, password) => {
    const data = await apiPost('/auth/login', { username, password }, true)
    if (data.mfa_required) return data
    const defaultPage = data.user?.role === 'admin' ? 'admin' : data.user?.role === 'lab' ? 'lab' : 'dashboard'
    const newState = { token: data.token, portal: data.portal, page: defaultPage }
    newState.csrfToken = data.csrf_token || ''
    newState.session = true
    setStoredAuth(newState)
    setAuthState(newState)
    setContext({ user: data.user, permissions: data.permissions || [], portal: data.portal })
    return data
  }

  const verifyMfa = async (challengeToken, code) => {
    const data = await apiPost('/auth/2fa/verify', { challenge_token: challengeToken, code }, true)
    const defaultPage = data.user?.role === 'admin' ? 'admin' : data.user?.role === 'lab' ? 'lab' : 'dashboard'
    const newState = { token: data.token, csrfToken: data.csrf_token || '', session: true, portal: data.portal, page: defaultPage }
    setStoredAuth(newState)
    setAuthState(newState)
    setContext({ user: data.user, permissions: data.permissions || [], portal: data.portal })
    return data
  }

  const register = async (payload) => {
    const data = await apiPost('/auth/register', payload, true)
    const newState = { token: data.token, csrfToken: data.csrf_token || '', session: true, portal: data.portal, page: 'dashboard' }
    setStoredAuth(newState)
    setAuthState(newState)
    setContext({ user: data.user, permissions: data.permissions || [], portal: data.portal })
    return data
  }

  const logout = async () => {
    try { if (authState.token) await apiPost('/auth/logout', undefined, false, { skipUnauthorizedHandler: true }) } catch { /* Clear local session even if server logout fails. */ }
    clearAuthState()
  }

  const updateStoredPage = useCallback((page) => {
    setAuthState(current => {
      const next = { ...current, page }
      setStoredAuth(next)
      return next
    })
  }, [])

  return (
    <AuthContext.Provider value={{
      authState, context, loading,
      user: context.user, permissions: context.permissions,
      isAdmin: context.user?.role === 'admin',
      isLab: context.user?.role === 'lab',
      isDoctor: context.user?.role === 'doctor',
      isPatient: context.user?.role === 'user',
      isAuthenticated: !!authState.token,
      login, verifyMfa, register, logout, updateStoredPage,
      setContext,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
