import { useState } from 'react'
import TimelineReplay from './TimelineReplay'
import OrderBookHeatmap from './OrderBookHeatmap'
import TradeStream from './TradeStream'
import CandlestickChart from './CandlestickChart'
import { mockReplayScenarios } from '../data/mockData'
import { Play, FileText, Clock, Zap } from 'lucide-react'

export default function ReplayPage() {
  const [activeScenario, setActiveScenario] = useState(null)

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <div>
        <h1 className="text-xl font-bold mb-1" style={{ color: '#e2e8f0' }}>Timeline Replay</h1>
        <p className="text-xs" style={{ color: '#64748b' }}>
          Replay historical incidents and analyze manipulation patterns
        </p>
      </div>

      {/* Scenario selection */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {mockReplayScenarios.map(scenario => (
          <button
            key={scenario.id}
            onClick={() => setActiveScenario(scenario)}
            className={`text-left p-3 rounded-lg border transition-all hover:brightness-110 ${
              activeScenario?.id === scenario.id ? 'border-cyan-500 bg-cyan-500/5' : ''
            }`}
            style={{
              borderColor: activeScenario?.id === scenario.id ? '#22d3ee' : '#2d3548',
              backgroundColor: activeScenario?.id === scenario.id ? 'rgba(34,211,238,0.05)' : '#161b22',
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              <Play className="w-3.5 h-3.5" style={{ color: '#22d3ee' }} />
              <span className="text-xs font-semibold" style={{ color: '#e2e8f0' }}>{scenario.name}</span>
            </div>
            <p className="text-[10px] mb-2" style={{ color: '#64748b' }}>{scenario.description}</p>
            <div className="flex items-center gap-3 text-[10px]" style={{ color: '#64748b' }}>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {scenario.duration_s}s
              </span>
              <span className="flex items-center gap-1">
                <Zap className="w-3 h-3" />
                {scenario.events} events
              </span>
            </div>
          </button>
        ))}
      </div>

      {/* Timeline */}
      <TimelineReplay />

      {/* Replay visualizations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ minHeight: 350 }}>
        <OrderBookHeatmap symbol="BTCUSDT" />
        <CandlestickChart symbol="BTCUSDT" />
      </div>
    </div>
  )
}
