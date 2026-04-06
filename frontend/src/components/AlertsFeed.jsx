import { useState, useEffect, useCallback } from 'react'
import { format } from 'date-fns'
import { AlertTriangle, Shield, ShieldAlert, ShieldOff, Info } from 'lucide-react'
import { generateAlerts } from '../data/mockData'
import useWebSocket from '../hooks/useWebSocket'

const severityConfig = {
  critical: { color: 'text-red-400', bg: 'bg-red-500/15', border: 'border-red-500/40', icon: ShieldOff, dot: 'bg-red-500' },
  high: { color: 'text-orange-400', bg: 'bg-orange-500/15', border: 'border-orange-500/40', icon: ShieldAlert, dot: 'bg-orange-500' },
  medium: { color: 'text-yellow-400', bg: 'bg-yellow-500/15', border: 'border-yellow-500/40', icon: AlertTriangle, dot: 'bg-yellow-500' },
  low: { color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-500/30', icon: Info, dot: 'bg-slate-500' },
}

const typeLabels = {
  spoofing: 'Spoofing',
  wash_trading: 'Wash Trade',
  layering: 'Layering',
  quote_stuffing: 'Quote Stuff',
  intent_mismatch: 'Mismatch',
}

export default function AlertsFeed({ onSelectAlert, limit = 20, compact = false }) {
  const [alerts, setAlerts] = useState(() => generateAlerts(30))

  const onMessage = useCallback((data) => {
    if (data.alert_type) {
      setAlerts(prev => [data, ...prev].slice(0, 100))
    }
  }, [])

  useWebSocket('/ws/alerts', { onMessage, enabled: true })

  // Simulate new alerts
  useEffect(() => {
    const interval = setInterval(() => {
      const newAlerts = generateAlerts(1)
      if (newAlerts[0]) {
        newAlerts[0].timestamp = new Date().toISOString()
        newAlerts[0].id = Date.now()
        setAlerts(prev => [newAlerts[0], ...prev].slice(0, 100))
      }
    }, 8000)
    return () => clearInterval(interval)
  }, [])

  const displayed = alerts.slice(0, limit)

  return (
    <div className={`rounded-lg border h-full flex flex-col ${compact ? 'p-3' : 'p-4'}`} style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>Alerts Feed</h3>
          <span className="text-xs" style={{ color: '#64748b' }}>
            {alerts.filter(a => a.severity === 'critical').length} critical &middot; {alerts.length} total
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse-dot" />
          <span className="text-[10px]" style={{ color: '#64748b' }}>Monitoring</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 space-y-1.5" style={{ maxHeight: compact ? 250 : 400 }}>
        {displayed.map((alert, i) => {
          const sev = severityConfig[alert.severity] || severityConfig.low
          const Icon = sev.icon
          const isNew = i === 0

          return (
            <button
              key={alert.id}
              onClick={() => onSelectAlert?.(alert)}
              className={`w-full text-left p-2.5 rounded-md border transition-all hover:brightness-110 cursor-pointer ${sev.bg} ${sev.border} ${isNew ? 'animate-fade-in' : ''}`}
              style={{ borderWidth: '1px' }}
            >
              <div className="flex items-start gap-2">
                <Icon className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${sev.color}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`text-xs font-semibold ${sev.color}`}>
                      {typeLabels[alert.alert_type] || alert.alert_type}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ backgroundColor: '#1c2333', color: '#94a3b8' }}>
                      {alert.symbol}
                    </span>
                    <span className="ml-auto text-[10px] font-mono" style={{ color: '#64748b' }}>
                      {format(new Date(alert.timestamp), 'HH:mm:ss')}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ backgroundColor: '#2d3548' }}>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${alert.confidence_score}%`,
                          backgroundColor: alert.confidence_score > 75 ? '#ef4444' : alert.confidence_score > 50 ? '#f97316' : '#eab308',
                        }}
                      />
                    </div>
                    <span className="text-[10px] font-mono shrink-0" style={{ color: '#94a3b8' }}>
                      {alert.confidence_score.toFixed(0)}%
                    </span>
                  </div>
                  {!compact && (
                    <p className="text-[11px] mt-1 line-clamp-1" style={{ color: '#64748b' }}>
                      {alert.explanation}
                    </p>
                  )}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
