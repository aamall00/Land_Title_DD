/**
 * API client — thin wrapper around fetch that:
 * 1. Prepends /api/v1
 * 2. Attaches the Supabase JWT from localStorage
 * 3. Throws on non-2xx responses with the error detail
 */

const BASE = '/api/v1'

async function getToken() {
  // Supabase stores session in localStorage
  const raw = localStorage.getItem(
    `sb-${import.meta.env.VITE_SUPABASE_URL?.split('//')[1]?.split('.')[0]}-auth-token`
  )
  if (!raw) return null
  try {
    const session = JSON.parse(raw)
    return session?.access_token ?? null
  } catch {
    return null
  }
}

async function request(method, path, { body, formData, params } = {}) {
  const token = await getToken()
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  let url = `${BASE}${path}`
  if (params) {
    const qs = new URLSearchParams(params).toString()
    if (qs) url += `?${qs}`
  }

  const init = { method, headers }
  if (formData) {
    init.body = formData
    // Don't set Content-Type — browser sets it with boundary
  } else if (body) {
    headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }

  const res = await fetch(url, init)
  if (res.status === 204) return null
  const data = await res.json()
  if (!res.ok) throw new Error(data?.detail ?? `HTTP ${res.status}`)
  return data
}

// ── Properties ─────────────────────────────────────────────────
export const api = {
  properties: {
    list:   ()          => request('GET',    '/properties'),
    get:    (id)        => request('GET',    `/properties/${id}`),
    create: (body)      => request('POST',   '/properties', { body }),
    update: (id, body)  => request('PATCH',  `/properties/${id}`, { body }),
    delete: (id)        => request('DELETE', `/properties/${id}`),
  },

  documents: {
    list:   (pid)           => request('GET',    `/properties/${pid}/documents`),
    get:    (pid, did)      => request('GET',    `/properties/${pid}/documents/${did}`),
    upload: (pid, formData) => request('POST',   `/properties/${pid}/documents`, { formData }),
    setType:(pid, did, doc_type) =>
      request('PATCH', `/properties/${pid}/documents/${did}/type`, { body: { doc_type } }),
    delete: (pid, did)      => request('DELETE', `/properties/${pid}/documents/${did}`),
  },

  queries: {
    ask:     (pid, body)   => request('POST', `/properties/${pid}/query`, { body }),
    history: (pid, limit)  =>
      request('GET', `/properties/${pid}/query/history`, { params: { limit } }),
  },

  reports: {
    list:     (pid)         => request('GET',  `/properties/${pid}/reports`),
    get:      (pid, rid)    => request('GET',  `/properties/${pid}/reports/${rid}`),
    generate: (pid, body)   => request('POST', `/properties/${pid}/reports`, { body }),
  },
}
