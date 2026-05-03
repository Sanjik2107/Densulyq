import { API_BASE, AUTH_STORAGE_KEY } from './utils.jsx'

let unauthorizedHandler = null

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = typeof handler === 'function' ? handler : null
}

function getToken() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return parsed.token || ''
  } catch { return '' }
}

function getCsrfToken() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return parsed.csrfToken || ''
  } catch { return '' }
}

function buildUrl(path) {
  const base = API_BASE.endsWith('/') ? API_BASE : API_BASE + '/'
  return new URL(String(path).replace(/^\/+/, ''), base)
}

async function request(path, options = {}) {
  const token = getToken()
  const csrfToken = getCsrfToken()
  const headers = { 'Content-Type': 'application/json' }
  if (!options.skipAuth && token) headers.Authorization = 'Bearer ' + token
  if (!options.skipAuth && csrfToken && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method || 'GET')) {
    headers['X-CSRF-Token'] = csrfToken
  }

  const url = buildUrl(path)
  if (options.params) {
    Object.entries(options.params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
    })
  }

  const res = await fetch(url.toString(), {
    method: options.method || 'GET',
    headers,
    credentials: 'include',
    body: options.payload ? JSON.stringify(options.payload) : undefined,
  })

  const text = await res.text()
  const data = (() => {
    try { return text ? JSON.parse(text) : {} } catch { return { detail: text } }
  })()

  if (!res.ok) {
    if (res.status === 401 && !options.skipUnauthorizedHandler && unauthorizedHandler) {
      unauthorizedHandler()
    }
    throw new Error(data.detail || 'HTTP ' + res.status)
  }
  return data
}

export const apiGet = (path, params, skipAuth, extra = {}) => request(path, { method: 'GET', params, skipAuth, ...extra })
export const apiPost = (path, payload, skipAuth, extra = {}) => request(path, { method: 'POST', payload, skipAuth, ...extra })
export const apiPut = (path, payload, extra = {}) => request(path, { method: 'PUT', payload, ...extra })
export const apiPatch = (path, payload, extra = {}) => request(path, { method: 'PATCH', payload, ...extra })
