import { useMemo } from 'react'

function getScoreColor(score) {
  if (score >= 75) return { ring: '#ef4444', bg: 'rgba(239,68,68,0.1)', text: 'text-red-400' }
  if (score >= 50) return { ring: '#f97316', bg: 'rgba(249,115,22,0.1)', text: 'text-orange-400' }
  if (score >= 25) return { ring: '#eab308', bg: 'rgba(234,179,8,0.1)', text: 'text-yellow-400' }
  return { ring: '#22c55e', bg: 'rgba(34,197,94,0.1)', text: 'text-green-400' }
}

function getLabel(score) {
  if (score >= 75) return 'Critical'
  if (score >= 50) return 'High'
  if (score >= 25) return 'Medium'
  return 'Low'
}

export default function RiskScore({ symbol, score = 0, trend, alerts24h, compact = false }) {
  const colors = useMemo(() => getScoreColor(score), [score])
  const circumference = 2 * Math.PI * 40
  const strokeDashoffset = circumference - (score / 100) * circumference

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <svg width="28" height="28" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#2d3548" strokeWidth="6" />
          <circle
            cx="50" cy="50" r="40" fill="none"
            stroke={colors.ring} strokeWidth="6"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            transform="rotate(-90 50 50)"
            style={{ transition: 'stroke-dashoffset 0.6s ease' }}
          />
          <text x="50" y="55" textAnchor="middle" fill={colors.ring} fontSize="28" fontWeight="bold" fontFamily="monospace">
            {score}
          </text>
        </svg>
        <span className={`text-xs font-medium ${colors.text}`}>{getLabel(score)}</span>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-4" style={{ borderColor: '#2d3548' }}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-text-primary">{symbol}</span>
        {trend && (
          <span className={`text-xs ${trend === 'up' ? 'text-red-400' : 'text-green-400'}`}>
            {trend === 'up' ? '▲' : '▼'} {trend === 'up' ? 'Rising' : 'Falling'}
          </span>
        )}
      </div>

      <div className="flex items-center justify-center">
        <svg width="100" height="100" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#2d3548" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="40" fill="none"
            stroke={colors.ring} strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            transform="rotate(-90 50 50)"
            style={{ transition: 'stroke-dashoffset 0.6s ease' }}
          />
          <text x="50" y="46" textAnchor="middle" fill={colors.ring} fontSize="22" fontWeight="bold" fontFamily="monospace">
            {score}
          </text>
          <text x="50" y="62" textAnchor="middle" fill="#94a3b8" fontSize="10">
            {getLabel(score)} Risk
          </text>
        </svg>
      </div>

      {alerts24h != null && (
        <div className="mt-3 text-center text-xs text-text-muted" style={{ color: '#64748b' }}>
          {alerts24h} alerts in 24h
        </div>
      )}
    </div>
  )
}
