/**
 * api/client.js — Axios HTTP client and WebSocket factory
 */

import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const WS_URL   = import.meta.env.VITE_WS_URL       || 'ws://localhost:8000'

// ── Axios instance ────────────────────────────────────────────────────────────
export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Unknown error'
    console.error('[API Error]', msg)
    return Promise.reject(new Error(msg))
  }
)

// ── Workflow endpoints ────────────────────────────────────────────────────────
export const workflowApi = {
  start:      (data)        => api.post('/workflows/', data),
  list:       (params = {}) => api.get('/workflows/', { params }),
  get:        (id)          => api.get(`/workflows/${id}`),
  stop:       (id)          => api.post(`/workflows/${id}/stop`),
  resume:     (id)          => api.post(`/workflows/${id}/resume`),
  delete:     (id)          => api.delete(`/workflows/${id}`),
  getAnalysis:(id)          => api.get(`/workflows/${id}/analysis`),
  triggerAnalysis: (id)     => api.post(`/workflows/${id}/analyze`),
  dashboard:  ()            => api.get('/workflows/dashboard'),
  active:     ()            => api.get('/workflows/active'),
  uploadFile: (formData, onProgress) => api.post('/workflows/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => onProgress && onProgress(Math.round(e.loaded / e.total * 100)),
  }),
}

// ── Log endpoints ─────────────────────────────────────────────────────────────
export const logApi = {
  getLogs:    (id, params = {}) => api.get(`/logs/${id}`, { params }),
  getSummary: (id)              => api.get(`/logs/${id}/summary`),
}

// ── Container endpoints ───────────────────────────────────────────────────────
export const containerApi = {
  list:     (params = {}) => api.get('/containers/', { params }),
  get:      (id)          => api.get(`/containers/${id}`),
  getLogs:  (id, tail)    => api.get(`/containers/${id}/logs`, { params: { tail } }),
  getStats: (id)          => api.get(`/containers/${id}/stats`),
  restart:  (id)          => api.post(`/containers/${id}/restart`),
  stop:     (id)          => api.post(`/containers/${id}/stop`),
  cleanup:  ()            => api.delete('/containers/cleanup'),
}

// ── WebSocket factory ─────────────────────────────────────────────────────────
export function createWebSocket(workflowId, handlers = {}) {
  const wsUrl = `${WS_URL}/ws/${workflowId}`
  const ws    = new WebSocket(wsUrl)

  ws.onopen    = () => handlers.onOpen?.()
  ws.onclose   = () => handlers.onClose?.()
  ws.onerror   = (e) => handlers.onError?.(e)
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      handlers.onMessage?.(data)

      // Dispatch typed handlers
      switch (data.type) {
        case 'log_line':             handlers.onLogLine?.(data); break
        case 'failure_detected':     handlers.onFailure?.(data); break
        case 'ai_analysis_complete': handlers.onAIAnalysis?.(data); break
        case 'status_update':        handlers.onStatusUpdate?.(data); break
      }
    } catch (err) {
      console.error('[WebSocket] JSON parse error:', err)
    }
  }

  // Heartbeat ping every 30s to keep connection alive
  const heartbeat = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }, 30_000)

  ws.closeWithCleanup = () => {
    clearInterval(heartbeat)
    ws.close()
  }

  return ws
}
