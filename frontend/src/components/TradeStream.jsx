import { useState, useEffect, useRef, useCallback } from 'react'
import { format } from 'date-fns'
import { generateTrades } from '../data/mockData'
import useWebSocket from '../hooks/useWebSocket'

export default function TradeStream({ symbol = 'BTCUSDT' }) {
  const [trades, setTrades] = useState(() => generateTrades(40, symbol))
  const listRef = useRef(null)
  const autoScrollRef = useRef(true)

  const onMessage = useCallback((data) => {
    if (data.price && data.quantity) {
      setTrades(prev => [data, ...prev].slice(0, 100))
    }
  }, [])

  const { status } = useWebSocket(`/ws/trades/${symbol.toLowerCase()}`, {
    onMessage,
    enabled: true,
  })

  // Simulate new trades when not connected
  useEffect(() => {
    if (status === 'connected') return
    const interval = setInterval(() => {
      const newTrades = generateTrades(1, symbol)
      setTrades(prev => [...newTrades, ...prev].slice(0, 100))
    }, 1500)
    return () => clearInterval(interval)
  }, [status, symbol])

  return (
    <div className="rounded-lg border p-4 h-full flex flex-col" style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>Trade Stream</h3>
          <span className="text-xs" style={{ color: '#64748b' }}>{symbol} &middot; {trades.length} trades</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${status === 'connected' ? 'bg-green-400 animate-pulse-dot' : 'bg-yellow-400'}`} />
          <span className="text-[10px]" style={{ color: '#64748b' }}>
            {status === 'connected' ? 'Live' : 'Simulated'}
          </span>
        </div>
      </div>

      {/* Header */}
      <div className="grid grid-cols-[1fr_1fr_1fr_70px] gap-2 text-[10px] font-medium pb-2 border-b" style={{ borderColor: '#2d3548', color: '#64748b' }}>
        <span>Price</span>
        <span className="text-right">Qty</span>
        <span className="text-right">Value</span>
        <span className="text-right">Time</span>
      </div>

      {/* Trade list */}
      <div ref={listRef} className="flex-1 overflow-y-auto min-h-0 mt-1" style={{ maxHeight: 300 }}>
        {trades.map((trade, i) => {
          const isBuy = trade.side === 'buy'
          const isNew = i === 0
          return (
            <div
              key={trade.id || i}
              className={`grid grid-cols-[1fr_1fr_1fr_70px] gap-2 py-1 text-xs font-mono items-center ${
                trade.suspicious ? 'bg-yellow-500/10 border-l-2 border-yellow-500' : ''
              } ${isNew ? 'animate-fade-in' : ''}`}
              style={{ borderBottom: '1px solid rgba(45,53,72,0.3)' }}
            >
              <span className={isBuy ? 'text-green-400' : 'text-red-400'}>
                ${trade.price?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
              <span className="text-right" style={{ color: '#e2e8f0' }}>
                {trade.quantity?.toFixed(4)}
              </span>
              <span className="text-right" style={{ color: '#94a3b8' }}>
                ${trade.value?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
              <span className="text-right" style={{ color: '#64748b' }}>
                {format(new Date(trade.timestamp), 'HH:mm:ss')}
              </span>
            </div>
          )
        })}
      </div>

      {/* Footer stats */}
      <div className="mt-2 pt-2 border-t flex justify-between text-[10px]" style={{ borderColor: '#2d3548', color: '#64748b' }}>
        <span>
          Buys: <span className="text-green-400 font-mono">{trades.filter(t => t.side === 'buy').length}</span>
        </span>
        <span>
          Sells: <span className="text-red-400 font-mono">{trades.filter(t => t.side === 'sell').length}</span>
        </span>
        <span>
          Suspicious: <span className="text-yellow-400 font-mono">{trades.filter(t => t.suspicious).length}</span>
        </span>
      </div>
    </div>
  )
}
