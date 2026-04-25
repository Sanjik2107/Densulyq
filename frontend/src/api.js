import { API_BASE, AUTH_STORAGE_KEY } from './utils.jsx'

function getToken() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return parsed.token || ''
  } catch { return '' }
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json' }
  if (!options.skipAuth && token) headers.Authorization = 'Bearer ' + token

  const url = new URL(API_BASE + path)
  if (options.params) {
    Object.entries(options.params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
    })
  }

  const res = await fetch(url.toString(), {
    method: options.method || 'GET',
    headers,
    body: options.payload ? JSON.stringify(options.payload) : undefined,
  })

  const text = await res.text()
  let data = {}
  try { data = text ? JSON.parse(text) : {} } catch { data = { detail: text } }

  if (!res.ok) throw new Error(data.detail || 'HTTP ' + res.status)
  return data
}

export const apiGet = (path, params, skipAuth) => request(path, { method: 'GET', params, skipAuth })
export const apiPost = (path, payload, skipAuth) => request(path, { method: 'POST', payload, skipAuth })
export const apiPut = (path, payload) => request(path, { method: 'PUT', payload })
