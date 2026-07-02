import axios from 'axios'

// Tenant resolution: ?tenant=slug wins (and is remembered), else last used,
// else 'demo'. In production each white-label domain sets X-Tenant at the
// reverse proxy and this becomes a no-op fallback.
const params = new URLSearchParams(window.location.search)
const fromUrl = params.get('tenant')
if (fromUrl) localStorage.setItem('tenant', fromUrl)
export const TENANT = fromUrl || localStorage.getItem('tenant') || 'demo'

export const api = axios.create({ baseURL: '/' })

api.interceptors.request.use((config) => {
  config.headers['X-Tenant'] = TENANT
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && localStorage.getItem('token')) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export const errText = (e) =>
  e.response?.data?.detail
    ? typeof e.response.data.detail === 'string'
      ? e.response.data.detail
      : JSON.stringify(e.response.data.detail)
    : e.message
