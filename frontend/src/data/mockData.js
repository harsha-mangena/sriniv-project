import { format, subMinutes, subHours, subSeconds } from 'date-fns'

const now = () => new Date()

// Helper to generate price levels around a base price
function generatePriceLevels(basePrice, side, levels = 20) {
  const result = []
  for (let i = 0; i < levels; i++) {
    const offset = (i + 1) * basePrice * 0.0001 * (0.8 + Math.random() * 0.4)
    const price = side === 'bid'
      ? basePrice - offset
      : basePrice + offset
    const quantity = Math.random() * 5 + 0.1
    const total = price * quantity
    result.push({
      price: parseFloat(price.toFixed(2)),
      quantity: parseFloat(quantity.toFixed(4)),
      total: parseFloat(total.toFixed(2)),
      orders: Math.floor(Math.random() * 15) + 1,
    })
  }
  return result
}

export function generateOrderBook(symbol = 'BTCUSDT') {
  const basePrice = symbol === 'BTCUSDT' ? 67432.50 : symbol === 'ETHUSDT' ? 3521.80 : 1.00
  return {
    symbol,
    timestamp: now().toISOString(),
    bids: generatePriceLevels(basePrice, 'bid', 25),
    asks: generatePriceLevels(basePrice, 'ask', 25),
    best_bid: parseFloat((basePrice - basePrice * 0.0001).toFixed(2)),
    best_ask: parseFloat((basePrice + basePrice * 0.0001).toFixed(2)),
    spread: parseFloat((basePrice * 0.0002).toFixed(2)),
  }
}

export function generateTrades(count = 50, symbol = 'BTCUSDT') {
  const basePrice = symbol === 'BTCUSDT' ? 67432.50 : 3521.80
  const trades = []
  for (let i = 0; i < count; i++) {
    const side = Math.random() > 0.5 ? 'buy' : 'sell'
    const price = basePrice + (Math.random() - 0.5) * basePrice * 0.002
    const quantity = Math.random() * 2 + 0.001
    const isSuspicious = Math.random() < 0.05
    trades.push({
      id: `T${Date.now()}-${i}`,
      trade_id: `${100000 + i}`,
      symbol,
      price: parseFloat(price.toFixed(2)),
      quantity: parseFloat(quantity.toFixed(6)),
      side,
      timestamp: subSeconds(now(), i * 3).toISOString(),
      suspicious: isSuspicious,
      value: parseFloat((price * quantity).toFixed(2)),
    })
  }
  return trades
}

const alertTypes = ['spoofing', 'wash_trading', 'layering', 'quote_stuffing', 'intent_mismatch']
const severities = ['low', 'medium', 'high', 'critical']
const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'XRPUSDT']

const explanations = {
  spoofing: [
    'Large buy orders placed 0.1% below best bid were canceled within 200ms after triggering sell-side executions. Pattern consistent with spoofing: deceptive orders to create false impression of demand.',
    'Detected rapid placement and cancellation of 15 orders on bid side within 500ms window. Orders were large (>2x average) and placed in descending price levels, creating artificial depth.',
    'A cluster of ask-side orders totaling 8.5 BTC appeared at 3 price levels, pulled within 150ms. Immediately followed by buy execution at depressed price.',
  ],
  wash_trading: [
    'Alternating buy-sell trades of nearly identical size (2.1±0.05 BTC) at 12-second intervals over 3 minutes. Volume recycling ratio: 94%. Consistent with self-trading to inflate volume.',
    'Detected symmetric trading loop: 5 buy/sell pairs with <1% size variance and regular 8s intervals. Trade loop symmetry score: 0.91.',
    'Circular flow detected: 3 sequential trades with matching sizes forming a closed loop. Time symmetry coefficient: 0.88. Net position change: ~0.',
  ],
  layering: [
    'Detected 8 orders stacked across 5 price levels on the ask side, all placed within 100ms. Synchronized cancellation of 87% of orders after opposite-side execution detected.',
    'Layered bid orders at levels $67,400-$67,420 created artificial support. All 12 orders canceled within 300ms once large sell order executed on the ask side.',
  ],
  quote_stuffing: [
    'Burst of 142 order/cancel events in 1-second window, far exceeding normal rate of 8/s. Pattern suggests intent to slow down other participants\' systems.',
    'Rapid-fire order submission: 95 orders placed and cancelled within 800ms. Order sizes were minimal, consistent with message-flooding strategy.',
  ],
  intent_mismatch: [
    'Order book showed strong bid-side support (+340 BTC cumulative bid volume), but actual execution was net sell (-12.3 BTC). Intent-outcome mismatch score: 0.87. Suggests deceptive order placement.',
    'Heavy ask-side pressure displayed (apparent sell intent), but realized trades were predominantly buys. Cosine similarity between intent and outcome vectors: 0.12.',
  ],
}

const detectorNames = {
  rule: ['cancel_rate_detector', 'order_lifetime_detector', 'book_pressure_detector', 'trade_loop_detector', 'symmetric_timing_detector', 'multi_level_stack_detector'],
  ml: ['isolation_forest', 'lstm_autoencoder'],
  custom: ['liquidity_mirage_score', 'layering_pressure_index', 'trade_loop_symmetry', 'book_shock_divergence', 'intent_outcome_mismatch'],
}

function randomDetectorScores(type) {
  const scores = {}
  const detectors = detectorNames[type]
  detectors.forEach(d => {
    if (Math.random() > 0.4) {
      scores[d] = parseFloat((Math.random() * 0.6 + 0.3).toFixed(3))
    }
  })
  return scores
}

function randomFeatures() {
  return {
    cancel_rate: parseFloat((Math.random() * 0.8 + 0.1).toFixed(4)),
    order_to_trade_ratio: parseFloat((Math.random() * 20 + 1).toFixed(2)),
    bid_ask_imbalance: parseFloat((Math.random() * 2 - 1).toFixed(4)),
    depth_concentration: parseFloat((Math.random()).toFixed(4)),
    order_arrival_burstiness: parseFloat((Math.random() * 5).toFixed(4)),
    avg_order_lifetime_ms: parseFloat((Math.random() * 2000 + 50).toFixed(0)),
    volume_entropy: parseFloat((Math.random() * 3).toFixed(4)),
    rolling_zscore_volume: parseFloat((Math.random() * 6 - 3).toFixed(4)),
    rolling_zscore_cancel: parseFloat((Math.random() * 6 - 3).toFixed(4)),
  }
}

export function generateAlerts(count = 30) {
  const alerts = []
  for (let i = 0; i < count; i++) {
    const alertType = alertTypes[Math.floor(Math.random() * alertTypes.length)]
    const severity = severities[Math.floor(Math.random() * severities.length)]
    const symbol = symbols[Math.floor(Math.random() * symbols.length)]
    const confidence = severity === 'critical' ? 75 + Math.random() * 25
      : severity === 'high' ? 55 + Math.random() * 30
      : severity === 'medium' ? 30 + Math.random() * 35
      : 10 + Math.random() * 30
    const typeExplanations = explanations[alertType]
    const explanation = typeExplanations[Math.floor(Math.random() * typeExplanations.length)]
    const ruleScores = randomDetectorScores('rule')
    const mlScores = randomDetectorScores('ml')
    const customScores = randomDetectorScores('custom')
    const features = randomFeatures()

    alerts.push({
      id: i + 1,
      symbol,
      alert_type: alertType,
      severity,
      confidence_score: parseFloat(confidence.toFixed(1)),
      rule_scores: ruleScores,
      ml_scores: mlScores,
      custom_scores: customScores,
      explanation,
      contributing_features: features,
      raw_evidence: {
        order_count: Math.floor(Math.random() * 50 + 5),
        trade_count: Math.floor(Math.random() * 20 + 1),
        window_duration_ms: Math.floor(Math.random() * 5000 + 500),
        affected_price_levels: Math.floor(Math.random() * 8 + 1),
        total_volume: parseFloat((Math.random() * 50 + 1).toFixed(4)),
        cancel_count: Math.floor(Math.random() * 40),
        execution_volume: parseFloat((Math.random() * 10).toFixed(4)),
      },
      timestamp: subMinutes(now(), i * 7 + Math.random() * 5).toISOString(),
      resolved: Math.random() < 0.2,
      created_at: subMinutes(now(), i * 7).toISOString(),
    })
  }
  return alerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
}

export function generateCandlesticks(count = 100, symbol = 'BTCUSDT') {
  const candles = []
  let basePrice = symbol === 'BTCUSDT' ? 67000 : 3500
  for (let i = count - 1; i >= 0; i--) {
    const open = basePrice + (Math.random() - 0.48) * basePrice * 0.003
    const close = open + (Math.random() - 0.48) * basePrice * 0.004
    const high = Math.max(open, close) + Math.random() * basePrice * 0.002
    const low = Math.min(open, close) - Math.random() * basePrice * 0.002
    const volume = Math.random() * 100 + 10
    const timestamp = subMinutes(now(), i * 5).toISOString()
    const isFlagged = Math.random() < 0.08

    candles.push({
      timestamp,
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume: parseFloat(volume.toFixed(2)),
      flagged: isFlagged,
    })
    basePrice = close
  }
  return candles
}

export function generateStats() {
  return {
    total_alerts_today: Math.floor(Math.random() * 40 + 15),
    critical_count: Math.floor(Math.random() * 5 + 1),
    high_count: Math.floor(Math.random() * 10 + 3),
    assets_monitored: 12,
    system_status: 'operational',
    events_processed_today: Math.floor(Math.random() * 100000 + 50000),
    avg_latency_ms: parseFloat((Math.random() * 15 + 2).toFixed(1)),
    uptime_percent: parseFloat((99 + Math.random()).toFixed(2)),
  }
}

export function generateRiskScores() {
  return symbols.map(symbol => ({
    symbol,
    score: Math.floor(Math.random() * 100),
    trend: Math.random() > 0.5 ? 'up' : 'down',
    alerts_24h: Math.floor(Math.random() * 15),
    last_alert: subHours(now(), Math.floor(Math.random() * 12)).toISOString(),
  }))
}

export const mockReplayScenarios = [
  { id: 'spoofing-btc-01', name: 'BTC Spoofing Event', description: 'Large bid spoofing on BTCUSDT detected 2024-03-15', duration_s: 120, events: 450 },
  { id: 'wash-eth-01', name: 'ETH Wash Trading', description: 'Symmetric wash trading loop on ETHUSDT', duration_s: 300, events: 890 },
  { id: 'layering-sol-01', name: 'SOL Layering Attack', description: 'Multi-level layering pattern on SOLUSDT', duration_s: 60, events: 230 },
  { id: 'stuffing-btc-01', name: 'BTC Quote Stuffing', description: 'High-frequency quote stuffing burst', duration_s: 10, events: 1500 },
]
