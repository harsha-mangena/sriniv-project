import { useState, useEffect, useCallback, useRef } from 'react'

export function useApi(fetcher, { immediate = true, deps = [] } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(immediate)
  const [error, setError] = useState(null)
  const mountedRef = useRef(true)

  const execute = useCallback(async (...args) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetcher(...args)
      if (mountedRef.current) {
        setData(result)
        setLoading(false)
      }
      return result
    } catch (err) {
      if (mountedRef.current) {
        setError(err)
        setLoading(false)
      }
      return null
    }
  }, [fetcher])

  useEffect(() => {
    mountedRef.current = true
    if (immediate) execute()
    return () => { mountedRef.current = false }
  }, deps)

  return { data, loading, error, execute, setData }
}

export function usePolling(fetcher, interval = 5000, { immediate = true } = {}) {
  const { data, loading, error, execute, setData } = useApi(fetcher, { immediate })

  useEffect(() => {
    if (!immediate) return
    const id = setInterval(execute, interval)
    return () => clearInterval(id)
  }, [execute, interval, immediate])

  return { data, loading, error, refresh: execute, setData }
}

export default useApi
