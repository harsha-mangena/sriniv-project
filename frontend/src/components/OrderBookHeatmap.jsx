import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { generateOrderBook } from '../data/mockData'
import useWebSocket from '../hooks/useWebSocket'

const ROWS = 20
const HISTORY_COLS = 40

function interpolateColor(value, side) {
  const intensity = Math.min(1, value)
  if (side === 'bid') {
    const r = Math.floor(6 + intensity * 16)
    const g = Math.floor(78 + intensity * 119)
    const b = Math.floor(20 + intensity * 54)
    return `rgb(${r},${g},${b})`
  }
  const r = Math.floor(100 + intensity * 139)
  const g = Math.floor(15 + intensity * 25)
  const b = Math.floor(15 + intensity * 25)
  return `rgb(${r},${g},${b})`
}

export default function OrderBookHeatmap({ symbol = 'BTCUSDT' }) {
  const canvasRef = useRef(null)
  const [orderBook, setOrderBook] = useState(() => generateOrderBook(symbol))
  const historyRef = useRef([])
  const animFrameRef = useRef(null)

  const onMessage = useCallback((data) => {
    if (data.bids && data.asks) setOrderBook(data)
  }, [])

  const { status } = useWebSocket(`/ws/orderbook/${symbol.toLowerCase()}`, {
    onMessage,
    enabled: true,
  })

  // Simulate updates when not connected
  useEffect(() => {
    if (status === 'connected') return
    const interval = setInterval(() => {
      setOrderBook(generateOrderBook(symbol))
    }, 800)
    return () => clearInterval(interval)
  }, [status, symbol])

  // Track history columns
  useEffect(() => {
    const maxQty = Math.max(
      ...orderBook.bids.slice(0, ROWS).map(b => b.quantity),
      ...orderBook.asks.slice(0, ROWS).map(a => a.quantity),
      0.001
    )

    const column = {
      bids: orderBook.bids.slice(0, ROWS).map(b => b.quantity / maxQty),
      asks: orderBook.asks.slice(0, ROWS).map(a => a.quantity / maxQty),
    }

    historyRef.current = [...historyRef.current.slice(-(HISTORY_COLS - 1)), column]
  }, [orderBook])

  // Canvas rendering
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1

    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)

    const width = rect.width
    const height = rect.height
    const history = historyRef.current
    const cols = history.length
    if (cols === 0) return

    const cellW = width / HISTORY_COLS
    const cellH = height / (ROWS * 2 + 1) // bids + gap + asks

    ctx.clearRect(0, 0, width, height)

    // Draw heatmap
    history.forEach((col, ci) => {
      const x = (HISTORY_COLS - cols + ci) * cellW

      // Asks (top, reversed so highest ask at top)
      col.asks.slice().reverse().forEach((val, ri) => {
        ctx.fillStyle = interpolateColor(val, 'ask')
        ctx.fillRect(x, ri * cellH, cellW - 0.5, cellH - 0.5)
      })

      // Bids (bottom)
      col.bids.forEach((val, ri) => {
        ctx.fillStyle = interpolateColor(val, 'bid')
        ctx.fillRect(x, (ROWS + 1 + ri) * cellH, cellW - 0.5, cellH - 0.5)
      })
    })

    // Draw spread line
    const spreadY = ROWS * cellH
    ctx.fillStyle = '#1c2333'
    ctx.fillRect(0, spreadY, width, cellH)
    ctx.fillStyle = '#94a3b8'
    ctx.font = '10px monospace'
    ctx.textAlign = 'center'
    ctx.fillText(`Spread: $${orderBook.spread?.toFixed(2) || '—'}`, width / 2, spreadY + cellH * 0.7)
  }, [orderBook])

  const bestBid = orderBook.best_bid
  const bestAsk = orderBook.best_ask
  const midPrice = ((bestBid + bestAsk) / 2).toFixed(2)

  return (
    <div className="rounded-lg border p-4 h-full flex flex-col" style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>Order Book Heatmap</h3>
          <span className="text-xs" style={{ color: '#64748b' }}>{symbol}</span>
        </div>
        <div className="flex items-center gap-3 text-xs font-mono">
          <div>
            <span style={{ color: '#64748b' }}>Bid </span>
            <span className="text-green-400">${bestBid?.toLocaleString()}</span>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>Ask </span>
            <span className="text-red-400">${bestAsk?.toLocaleString()}</span>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>Mid </span>
            <span className="text-cyan-400">${midPrice}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${status === 'connected' ? 'bg-green-400 animate-pulse-dot' : 'bg-yellow-400'}`} />
          <span className="text-[10px]" style={{ color: '#64748b' }}>
            {status === 'connected' ? 'Live' : 'Simulated'}
          </span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mb-2 text-[10px]" style={{ color: '#64748b' }}>
        <div className="flex items-center gap-1">
          <div className="w-3 h-2 rounded-sm" style={{ backgroundColor: 'rgb(22,197,74)' }} />
          <span>Bids (volume)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-2 rounded-sm" style={{ backgroundColor: 'rgb(239,40,40)' }} />
          <span>Asks (volume)</span>
        </div>
        <span className="ml-auto">← time</span>
      </div>

      <canvas
        ref={canvasRef}
        className="flex-1 w-full rounded"
        style={{ minHeight: 200, backgroundColor: '#0f1117' }}
      />

      {/* Depth summary */}
      <div className="mt-2 grid grid-cols-2 gap-2 text-[10px]">
        <div className="flex items-center justify-between px-2 py-1 rounded" style={{ backgroundColor: 'rgba(34,197,94,0.08)' }}>
          <span style={{ color: '#64748b' }}>Bid Depth</span>
          <span className="font-mono text-green-400">
            {orderBook.bids.slice(0, 10).reduce((s, b) => s + b.quantity, 0).toFixed(2)}
          </span>
        </div>
        <div className="flex items-center justify-between px-2 py-1 rounded" style={{ backgroundColor: 'rgba(239,68,68,0.08)' }}>
          <span style={{ color: '#64748b' }}>Ask Depth</span>
          <span className="font-mono text-red-400">
            {orderBook.asks.slice(0, 10).reduce((s, a) => s + a.quantity, 0).toFixed(2)}
          </span>
        </div>
      </div>
    </div>
  )
}
