import { useEffect, useRef, useState, useCallback } from 'react'

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000'

export function useWebSocket(path, { onMessage, enabled = true, reconnectInterval = 3000 } = {}) {
  const [status, setStatus] = useState('disconnected') // 'connecting' | 'connected' | 'disconnected' | 'error'
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const onMessageRef = useRef(onMessage)
  const mountedRef = useRef(true)

  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (!enabled || !mountedRef.current) return

    try {
      const url = `${WS_BASE}${path}`
      setStatus('connecting')
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (mountedRef.current) setStatus('connected')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessageRef.current?.(data)
        } catch {
          onMessageRef.current?.(event.data)
        }
      }

      ws.onerror = () => {
        if (mountedRef.current) setStatus('error')
      }

      ws.onclose = () => {
        if (mountedRef.current) {
          setStatus('disconnected')
          reconnectTimer.current = setTimeout(connect, reconnectInterval)
        }
      }
    } catch {
      if (mountedRef.current) {
        setStatus('error')
        reconnectTimer.current = setTimeout(connect, reconnectInterval)
      }
    }
  }, [path, enabled, reconnectInterval])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      clearTimeout(reconnectTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [connect])

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  return { status, send }
}

export default useWebSocket
