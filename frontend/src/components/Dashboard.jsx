import { useState, useEffect } from 'react'
import { Activity, AlertTriangle, Shield, Zap, Clock, Server } from 'lucide-react'
import OrderBookHeatmap from './OrderBookHeatmap'
import TradeStream from './TradeStream'
import AlertsFeed from './AlertsFeed'
import CandlestickChart from './CandlestickChart'
import EventDetail from './EventDetail'
import RiskScore from './RiskScore'
import { generateStats, generateRiskScores } from '../data/mockData'

function StatCard({ icon: Icon, label, value, sub, color = '#22d3ee' }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-lg border" style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
      <div className="p-2 rounded-md" style={{ backgroundColor: color + '15' }}>
        <Icon className="w-4 h-4" style={{ color }} />
      </div>
      <div>
        <div className="text-lg font-bold font-mono" style={{ color: '#e2e8f0' }}>{value}</div>
        <div className="text-[10px]" style={{ color: '#64748b' }}>{label}</div>
      </div>
      {sub && <span className="ml-auto text-xs font-mono" style={{ color }}>{sub}</span>}
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(() => generateStats())
  const [riskScores, setRiskScores] = useState(() => generateRiskScores())
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [activeSymbol] = useState('BTCUSDT')

  // Refresh stats periodically
  useEffect(() => {
    const interval = setInterval(() => setStats(generateStats()), 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-3">
        <StatCard
          icon={AlertTriangle}
          label="Alerts Today"
          value={stats.total_alerts_today}
          color="#f97316"
        />
        <StatCard
          icon={Shield}
          label="Critical"
          value={stats.critical_count}
          sub={`+${stats.high_count} high`}
          color="#ef4444"
        />
        <StatCard
          icon={Activity}
          label="Assets Monitored"
          value={stats.assets_monitored}
          color="#3b82f6"
        />
        <StatCard
          icon={Server}
          label="System Status"
          value={stats.system_status === 'operational' ? 'Online' : 'Degraded'}
          sub={`${stats.uptime_percent}%`}
          color={stats.system_status === 'operational' ? '#22c55e' : '#ef4444'}
        />
        <StatCard
          icon={Zap}
          label="Events Processed"
          value={(stats.events_processed_today / 1000).toFixed(1) + 'k'}
          color="#a855f7"
        />
        <StatCard
          icon={Clock}
          label="Avg Latency"
          value={stats.avg_latency_ms + 'ms'}
          color="#22d3ee"
        />
      </div>

      {/* Risk Scores Row */}
      <div className="flex gap-3 overflow-x-auto pb-1">
        {riskScores.map(rs => (
          <div key={rs.symbol} className="shrink-0">
            <RiskScore {...rs} />
          </div>
        ))}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ minHeight: 400 }}>
        <OrderBookHeatmap symbol={activeSymbol} />
        <TradeStream symbol={activeSymbol} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ minHeight: 350 }}>
        <AlertsFeed onSelectAlert={setSelectedAlert} limit={15} />
        <CandlestickChart symbol={activeSymbol} />
      </div>

      {/* Event Detail Drawer */}
      {selectedAlert && (
        <EventDetail alert={selectedAlert} onClose={() => setSelectedAlert(null)} />
      )}
    </div>
  )
}
