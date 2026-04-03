const BASE = '/api'

async function req(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

function withQuery(path, params = {}) {
  const search = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) return
    if (typeof value === 'string' && value.trim() === '') return
    search.set(key, String(value))
  })

  const query = search.toString()
  return query ? `${path}?${query}` : path
}

export const api = {
  health:        ()           => req('/health'),
  getLaws:       (params={})  => req(withQuery('/laws', params)),
  getLaw:        (code, params={}) => req(withQuery(`/laws/${encodeURIComponent(code)}`, params)),
  getCategories: ()           => req('/categories'),
  getCategoryStats: ()        => req('/categories/stats'),
  analyze:       (body)       => req('/analyze',          { method:'POST', body }),
  createSession: ()           => req('/chat/session',     { method:'POST', body:{} }),
  chat:          (body)       => req('/chat',             { method:'POST', body }),
  getHistory:    (sid)        => req(`/chat/${sid}/history`),
}
