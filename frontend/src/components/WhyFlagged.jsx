import { AlertTriangle, TrendingUp, Search, CheckCircle2 } from 'lucide-react'

const detectorLabels = {
  cancel_rate_detector: 'Cancel Rate',
  order_lifetime_detector: 'Order Lifetime',
  book_pressure_detector: 'Book Pressure',
  trade_loop_detector: 'Trade Loop',
  symmetric_timing_detector: 'Symmetric Timing',
  multi_level_stack_detector: 'Multi-Level Stack',
  isolation_forest: 'Isolation Forest',
  lstm_autoencoder: 'LSTM Autoencoder',
  liquidity_mirage_score: 'Liquidity Mirage',
  layering_pressure_index: 'Layering Pressure',
  trade_loop_symmetry: 'Trade Loop Symmetry',
  book_shock_divergence: 'Book Shock Divergence',
  intent_outcome_mismatch: 'Intent-Outcome Mismatch',
}

const featureNormalRanges = {
  cancel_rate: { min: 0.05, max: 0.25, label: 'Cancel Rate' },
  order_to_trade_ratio: { min: 2, max: 8, label: 'Order-to-Trade Ratio' },
  bid_ask_imbalance: { min: -0.3, max: 0.3, label: 'Bid/Ask Imbalance' },
  depth_concentration: { min: 0.1, max: 0.5, label: 'Depth Concentration' },
  order_arrival_burstiness: { min: 0.2, max: 1.5, label: 'Order Burstiness' },
  avg_order_lifetime_ms: { min: 500, max: 5000, label: 'Avg Order Lifetime (ms)' },
  volume_entropy: { min: 1.0, max: 2.5, label: 'Volume Entropy' },
  rolling_zscore_volume: { min: -2, max: 2, label: 'Volume Z-Score' },
  rolling_zscore_cancel: { min: -2, max: 2, label: 'Cancel Z-Score' },
}

const investigationSteps = {
  spoofing: [
    'Review order placement and cancellation timestamps',
    'Check if canceled orders were within top-of-book proximity',
    'Verify if opposite-side executions followed cancellations',
    'Analyze order sizes relative to historical norms',
    'Cross-reference with known spoofing entity patterns',
  ],
  wash_trading: [
    'Examine trade size symmetry and timing patterns',
    'Check for counterparty relationships or clustering',
    'Calculate net position change over the window',
    'Review volume recycling ratio',
    'Compare trade frequency to historical baseline',
  ],
  layering: [
    'Map order placement across price levels',
    'Verify synchronized cancellation timing',
    'Check opposite-side execution correlation',
    'Analyze order cluster density and persistence',
    'Review price impact before and after layered orders',
  ],
  quote_stuffing: [
    'Measure order/cancel event frequency',
    'Compare message rate to normal baseline',
    'Check for minimal order sizes (message-flooding pattern)',
    'Analyze impact on other market participants',
    'Review exchange message rate limits',
  ],
  intent_mismatch: [
    'Compare order book intent signal vs realized execution direction',
    'Analyze bid/ask pressure vs actual trade flow',
    'Compute cosine similarity between intent and outcome vectors',
    'Identify pseudo-entity patterns in order clustering',
    'Review price movement relative to displayed intent',
  ],
}

export default function WhyFlagged({ alert }) {
  if (!alert) return null

  const firedDetectors = [
    ...Object.entries(alert.rule_scores || {}).map(([k, v]) => ({ name: k, score: v, type: 'rule' })),
    ...Object.entries(alert.ml_scores || {}).map(([k, v]) => ({ name: k, score: v, type: 'ml' })),
    ...Object.entries(alert.custom_scores || {}).map(([k, v]) => ({ name: k, score: v, type: 'custom' })),
  ].sort((a, b) => b.score - a.score)

  const abnormalFeatures = Object.entries(alert.contributing_features || {})
    .filter(([key, value]) => {
      const range = featureNormalRanges[key]
      return range && (value < range.min || value > range.max)
    })
    .sort((a, b) => {
      const rangeA = featureNormalRanges[a[0]]
      const rangeB = featureNormalRanges[b[0]]
      const devA = Math.max(0, a[1] - rangeA.max, rangeA.min - a[1]) / (rangeA.max - rangeA.min)
      const devB = Math.max(0, b[1] - rangeB.max, rangeB.min - b[1]) / (rangeB.max - rangeB.min)
      return devB - devA
    })

  const steps = investigationSteps[alert.alert_type] || investigationSteps.spoofing

  const typeColor = {
    rule: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    ml: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    custom: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  }

  return (
    <div className="space-y-5">
      {/* Fired Detectors */}
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: '#94a3b8' }}>
          <AlertTriangle className="w-3.5 h-3.5" />
          Detectors Fired ({firedDetectors.length})
        </h4>
        <div className="space-y-2">
          {firedDetectors.map(({ name, score, type }) => (
            <div key={name} className="flex items-center gap-2">
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${typeColor[type]}`}>
                {type}
              </span>
              <span className="text-xs flex-1 truncate" style={{ color: '#e2e8f0' }}>
                {detectorLabels[name] || name}
              </span>
              <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: '#2d3548' }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${score * 100}%`,
                    backgroundColor: score > 0.7 ? '#ef4444' : score > 0.4 ? '#f97316' : '#eab308',
                  }}
                />
              </div>
              <span className="text-xs font-mono w-10 text-right" style={{ color: '#94a3b8' }}>
                {(score * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Abnormal Features */}
      {abnormalFeatures.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: '#94a3b8' }}>
            <TrendingUp className="w-3.5 h-3.5" />
            Abnormal Features ({abnormalFeatures.length})
          </h4>
          <div className="space-y-3">
            {abnormalFeatures.map(([key, value]) => {
              const range = featureNormalRanges[key]
              if (!range) return null
              const totalSpan = range.max - range.min
              const normalStart = 0.2
              const normalEnd = 0.8
              const valuePos = Math.max(0, Math.min(1, (value - (range.min - totalSpan * 0.5)) / (totalSpan * 2)))
              const isHigh = value > range.max

              return (
                <div key={key}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs" style={{ color: '#e2e8f0' }}>{range.label}</span>
                    <span className="text-xs font-mono" style={{ color: isHigh ? '#ef4444' : '#eab308' }}>
                      {typeof value === 'number' ? value.toFixed(4) : value}
                    </span>
                  </div>
                  <div className="relative h-2 rounded-full overflow-hidden" style={{ backgroundColor: '#2d3548' }}>
                    {/* Normal range indicator */}
                    <div
                      className="absolute h-full opacity-30"
                      style={{
                        left: `${normalStart * 100}%`,
                        width: `${(normalEnd - normalStart) * 100}%`,
                        backgroundColor: '#22c55e',
                      }}
                    />
                    {/* Current value marker */}
                    <div
                      className="absolute top-0 w-1.5 h-full rounded-full"
                      style={{
                        left: `${valuePos * 100}%`,
                        backgroundColor: isHigh ? '#ef4444' : '#eab308',
                        boxShadow: `0 0 4px ${isHigh ? '#ef4444' : '#eab308'}`,
                      }}
                    />
                  </div>
                  <div className="flex justify-between mt-0.5">
                    <span className="text-[10px]" style={{ color: '#64748b' }}>Normal: {range.min}</span>
                    <span className="text-[10px]" style={{ color: '#64748b' }}>{range.max}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Pattern Description */}
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-2" style={{ color: '#94a3b8' }}>
          <Search className="w-3.5 h-3.5" />
          Pattern Description
        </h4>
        <p className="text-xs leading-relaxed" style={{ color: '#94a3b8' }}>
          {alert.explanation}
        </p>
      </div>

      {/* Investigation Steps */}
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-2" style={{ color: '#94a3b8' }}>
          <CheckCircle2 className="w-3.5 h-3.5" />
          Suggested Investigation Steps
        </h4>
        <ol className="space-y-1.5">
          {steps.map((step, i) => (
            <li key={i} className="flex items-start gap-2 text-xs" style={{ color: '#94a3b8' }}>
              <span className="font-mono text-cyan-400 mt-0.5 shrink-0">{i + 1}.</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}
