import { format } from 'date-fns'
import { X, Clock, Target, BarChart3, Brain, Cpu, FileText } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import WhyFlagged from './WhyFlagged'
import RiskScore from './RiskScore'

const severityColors = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#64748b',
}

const typeLabels = {
  spoofing: 'Spoofing',
  wash_trading: 'Wash Trading',
  layering: 'Layering',
  quote_stuffing: 'Quote Stuffing',
  intent_mismatch: 'Intent-Outcome Mismatch',
}

function ConfidenceGauge({ score }) {
  const radius = 50
  const circumference = Math.PI * radius // semi-circle
  const offset = circumference - (score / 100) * circumference
  const color = score > 75 ? '#ef4444' : score > 50 ? '#f97316' : score > 25 ? '#eab308' : '#22c55e'

  return (
    <div className="flex flex-col items-center">
      <svg width="120" height="70" viewBox="0 0 120 70">
        <path
          d="M 10 65 A 50 50 0 0 1 110 65"
          fill="none" stroke="#2d3548" strokeWidth="8" strokeLinecap="round"
        />
        <path
          d="M 10 65 A 50 50 0 0 1 110 65"
          fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
        <text x="60" y="58" textAnchor="middle" fill={color} fontSize="20" fontWeight="bold" fontFamily="monospace">
          {score.toFixed(1)}
        </text>
        <text x="60" y="68" textAnchor="middle" fill="#64748b" fontSize="8">
          confidence
        </text>
      </svg>
    </div>
  )
}

function ScoreBar({ label, score, color }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs w-28 truncate" style={{ color: '#94a3b8' }}>{label}</span>
      <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ backgroundColor: '#2d3548' }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${score * 100}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-mono w-10 text-right" style={{ color: '#e2e8f0' }}>
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  )
}

export default function EventDetail({ alert, onClose }) {
  if (!alert) return null

  const featureData = Object.entries(alert.contributing_features || {})
    .slice(0, 10)
    .map(([key, value]) => ({
      name: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      value: Math.abs(value),
      original: value,
    }))
    .sort((a, b) => b.value - a.value)

  const ruleScoreEntries = Object.entries(alert.rule_scores || {})
  const mlScoreEntries = Object.entries(alert.ml_scores || {})
  const customScoreEntries = Object.entries(alert.custom_scores || {})

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/60" onClick={onClose} />

      {/* Drawer */}
      <div
        className="w-[520px] max-w-full h-full overflow-y-auto animate-slide-in-right"
        style={{ backgroundColor: '#161b22', borderLeft: '1px solid #2d3548' }}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 p-4 flex items-center justify-between" style={{ backgroundColor: '#161b22', borderBottom: '1px solid #2d3548' }}>
          <div className="flex items-center gap-3">
            <div
              className="px-2.5 py-1 rounded text-xs font-bold uppercase"
              style={{
                backgroundColor: severityColors[alert.severity] + '20',
                color: severityColors[alert.severity],
                border: `1px solid ${severityColors[alert.severity]}40`,
              }}
            >
              {alert.severity}
            </div>
            <div>
              <h2 className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>
                {typeLabels[alert.alert_type] || alert.alert_type}
              </h2>
              <span className="text-xs font-mono" style={{ color: '#64748b' }}>{alert.symbol} &middot; #{alert.id}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-white/5 transition-colors"
            style={{ color: '#64748b' }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-6">
          {/* Confidence Gauge + Metadata */}
          <div className="flex items-start gap-4">
            <ConfidenceGauge score={alert.confidence_score} />
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-2 text-xs" style={{ color: '#94a3b8' }}>
                <Clock className="w-3.5 h-3.5" />
                {format(new Date(alert.timestamp), 'yyyy-MM-dd HH:mm:ss.SSS')}
              </div>
              <div className="flex items-center gap-2 text-xs" style={{ color: '#94a3b8' }}>
                <Target className="w-3.5 h-3.5" />
                Window: {alert.raw_evidence?.window_duration_ms || 0}ms
              </div>
              <div className="flex items-center gap-2 text-xs" style={{ color: '#94a3b8' }}>
                <FileText className="w-3.5 h-3.5" />
                {alert.raw_evidence?.order_count || 0} orders, {alert.raw_evidence?.trade_count || 0} trades
              </div>
            </div>
          </div>

          {/* Explanation */}
          <div className="rounded-lg p-3" style={{ backgroundColor: '#1c2333', border: '1px solid #2d3548' }}>
            <p className="text-xs leading-relaxed" style={{ color: '#e2e8f0' }}>
              {alert.explanation}
            </p>
          </div>

          {/* Rule Detector Scores */}
          {ruleScoreEntries.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-2" style={{ color: '#94a3b8' }}>
                <BarChart3 className="w-3.5 h-3.5 text-blue-400" />
                Rule Detector Scores
              </h4>
              <div className="space-y-1.5">
                {ruleScoreEntries.map(([name, score]) => (
                  <ScoreBar key={name} label={name.replace(/_/g, ' ')} score={score} color="#3b82f6" />
                ))}
              </div>
            </div>
          )}

          {/* ML Scores */}
          {mlScoreEntries.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-2" style={{ color: '#94a3b8' }}>
                <Brain className="w-3.5 h-3.5 text-purple-400" />
                ML Anomaly Scores
              </h4>
              <div className="space-y-1.5">
                {mlScoreEntries.map(([name, score]) => (
                  <ScoreBar key={name} label={name.replace(/_/g, ' ')} score={score} color="#a855f7" />
                ))}
              </div>
            </div>
          )}

          {/* Custom Algorithm Scores */}
          {customScoreEntries.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-2" style={{ color: '#94a3b8' }}>
                <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                Custom Algorithm Scores
              </h4>
              <div className="space-y-1.5">
                {customScoreEntries.map(([name, score]) => (
                  <ScoreBar key={name} label={name.replace(/_/g, ' ')} score={score} color="#22d3ee" />
                ))}
              </div>
            </div>
          )}

          {/* Contributing Features Bar Chart */}
          {featureData.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: '#94a3b8' }}>
                Contributing Features
              </h4>
              <div className="rounded-lg p-2" style={{ backgroundColor: '#0f1117' }}>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={featureData} layout="vertical" margin={{ left: 80, right: 20, top: 5, bottom: 5 }}>
                    <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tick={{ fill: '#94a3b8', fontSize: 9 }}
                      axisLine={false}
                      tickLine={false}
                      width={80}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1c2333', border: '1px solid #2d3548', borderRadius: 6, fontSize: 11 }}
                      labelStyle={{ color: '#e2e8f0' }}
                      itemStyle={{ color: '#94a3b8' }}
                    />
                    <Bar dataKey="value" radius={[0, 3, 3, 0]}>
                      {featureData.map((entry, i) => (
                        <Cell key={i} fill={entry.original > 0 ? '#3b82f6' : '#ef4444'} fillOpacity={0.7} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Why Flagged (full analysis) */}
          <div className="border-t pt-4" style={{ borderColor: '#2d3548' }}>
            <WhyFlagged alert={alert} />
          </div>

          {/* Raw Evidence */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: '#94a3b8' }}>
              Raw Evidence
            </h4>
            <pre
              className="text-[10px] font-mono p-3 rounded-lg overflow-x-auto"
              style={{ backgroundColor: '#0f1117', color: '#94a3b8', border: '1px solid #2d3548' }}
            >
              {JSON.stringify(alert.raw_evidence, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
