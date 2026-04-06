const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`
  const config = {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  }

  const response = await fetch(url, config)
  if (!response.ok) {
    const error = new Error(`API error: ${response.status} ${response.statusText}`)
    error.status = response.status
    error.response = response
    throw error
  }
  return response.json()
}

export const api = {
  getHealth: () => request('/api/health'),
  getStats: () => request('/api/stats'),
  getAlerts: (params = {}) => {
    const query = new URLSearchParams()
    if (params.symbol) query.set('symbol', params.symbol)
    if (params.alert_type) query.set('alert_type', params.alert_type)
    if (params.severity) query.set('severity', params.severity)
    if (params.min_confidence) query.set('min_confidence', params.min_confidence)
    if (params.start_time) query.set('start_time', params.start_time)
    if (params.end_time) query.set('end_time', params.end_time)
    if (params.limit) query.set('limit', params.limit)
    if (params.offset) query.set('offset', params.offset)
    const qs = query.toString()
    return request(`/api/alerts${qs ? `?${qs}` : ''}`)
  },
  getAlert: (id) => request(`/api/alerts/${id}`),
  getOrderBook: (symbol) => request(`/api/orderbook/${symbol}`),
  getTrades: (symbol) => request(`/api/trades/${symbol}`),
  getFeatures: (symbol) => request(`/api/features/${symbol}`),
  startReplay: (data) => request('/api/replay/start', { method: 'POST', body: JSON.stringify(data) }),
  injectEvent: (data) => request('/api/replay/inject', { method: 'POST', body: JSON.stringify(data) }),
}

export default api
