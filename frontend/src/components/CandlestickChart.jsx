import { useState, useMemo } from 'react'
import { format } from 'date-fns'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceArea, CartesianGrid, ReferenceLine
} from 'recharts'
import { generateCandlesticks } from '../data/mockData'

function CustomCandlestick({ x, y, width, height, payload }) {
  if (!payload) return null
  const { open, close, high, low } = payload
  const isUp = close >= open
  const color = isUp ? '#22c55e' : '#ef4444'
  const bodyTop = Math.min(open, close)
  const bodyBottom = Math.max(open, close)

  // We need to work in the chart's coordinate system
  // The y and height we get are for the 'close' bar
  // We'll render our own candlestick shape
  return null // We use custom rendering instead
}

export default function CandlestickChart({ symbol = 'BTCUSDT' }) {
  const [candles] = useState(() => generateCandlesticks(80, symbol))
  const [zoomStart, setZoomStart] = useState(null)
  const [zoomEnd, setZoomEnd] = useState(null)
  const [viewRange, setViewRange] = useState([0, candles.length])

  const displayedCandles = useMemo(() => {
    return candles.slice(viewRange[0], viewRange[1]).map((c, i) => {
      const isUp = c.close >= c.open
      return {
        ...c,
        idx: i,
        timeLabel: format(new Date(c.timestamp), 'HH:mm'),
        // For the bar chart: we draw a bar from low to high, and overlay body
        bodyBottom: Math.min(c.open, c.close),
        bodyTop: Math.max(c.open, c.close),
        bodyHeight: Math.abs(c.close - c.open),
        wickRange: [c.low, c.high],
        color: isUp ? '#22c55e' : '#ef4444',
        isUp,
      }
    })
  }, [candles, viewRange])

  const flaggedRegions = useMemo(() => {
    const regions = []
    let start = null
    displayedCandles.forEach((c, i) => {
      if (c.flagged && start === null) start = i
      if (!c.flagged && start !== null) {
        regions.push({ start, end: i - 1 })
        start = null
      }
    })
    if (start !== null) regions.push({ start, end: displayedCandles.length - 1 })
    return regions
  }, [displayedCandles])

  const priceMin = Math.min(...displayedCandles.map(c => c.low)) * 0.9999
  const priceMax = Math.max(...displayedCandles.map(c => c.high)) * 1.0001

  const CustomTooltipContent = ({ active, payload }) => {
    if (!active || !payload?.[0]) return null
    const data = payload[0].payload
    return (
      <div className="rounded-md p-2 text-[10px] font-mono" style={{ backgroundColor: '#1c2333', border: '1px solid #2d3548' }}>
        <div style={{ color: '#e2e8f0' }}>{format(new Date(data.timestamp), 'MMM dd HH:mm')}</div>
        <div className="grid grid-cols-2 gap-x-3 mt-1">
          <span style={{ color: '#64748b' }}>O</span><span style={{ color: data.isUp ? '#22c55e' : '#ef4444' }}>${data.open?.toLocaleString()}</span>
          <span style={{ color: '#64748b' }}>H</span><span style={{ color: '#e2e8f0' }}>${data.high?.toLocaleString()}</span>
          <span style={{ color: '#64748b' }}>L</span><span style={{ color: '#e2e8f0' }}>${data.low?.toLocaleString()}</span>
          <span style={{ color: '#64748b' }}>C</span><span style={{ color: data.isUp ? '#22c55e' : '#ef4444' }}>${data.close?.toLocaleString()}</span>
          <span style={{ color: '#64748b' }}>Vol</span><span style={{ color: '#94a3b8' }}>{data.volume?.toFixed(1)}</span>
        </div>
        {data.flagged && <div className="text-yellow-400 mt-1">&#9888; Flagged region</div>}
      </div>
    )
  }

  // Create bar data for rendering pseudo-candlesticks using stacked bars
  const chartData = displayedCandles.map(c => ({
    ...c,
    // For stacked bar: invisible base + body
    base: c.bodyBottom,
    body: c.bodyHeight || priceMax * 0.00005,
    wickLow: c.low,
    wickHigh: c.high,
  }))

  return (
    <div className="rounded-lg border p-4 h-full flex flex-col" style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>Price Chart</h3>
          <span className="text-xs" style={{ color: '#64748b' }}>{symbol} &middot; 5m candles</span>
        </div>
        <div className="flex gap-1">
          {['1H', '4H', '1D'].map(tf => (
            <button
              key={tf}
              className="px-2 py-0.5 text-[10px] rounded border transition-colors hover:border-cyan-500 hover:text-cyan-400"
              style={{ borderColor: '#2d3548', color: '#64748b' }}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Main chart */}
      <div className="flex-1" style={{ minHeight: 180 }}>
        <ResponsiveContainer width="100%" height="75%">
          <ComposedChart data={chartData} margin={{ top: 5, right: 5, bottom: 0, left: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1c2333" />
            <XAxis
              dataKey="timeLabel"
              tick={{ fill: '#64748b', fontSize: 9 }}
              axisLine={{ stroke: '#2d3548' }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[priceMin, priceMax]}
              tick={{ fill: '#64748b', fontSize: 9 }}
              axisLine={{ stroke: '#2d3548' }}
              tickLine={false}
              tickFormatter={v => `$${(v / 1000).toFixed(1)}k`}
              width={55}
            />
            <Tooltip content={<CustomTooltipContent />} />

            {/* Flagged regions */}
            {flaggedRegions.map((r, i) => (
              <ReferenceArea
                key={i}
                x1={chartData[r.start]?.timeLabel}
                x2={chartData[r.end]?.timeLabel}
                fill="#ef4444"
                fillOpacity={0.08}
                stroke="#ef4444"
                strokeOpacity={0.2}
                strokeDasharray="3 3"
              />
            ))}

            {/* Invisible base */}
            <Bar dataKey="base" stackId="candle" fill="transparent" isAnimationActive={false} />

            {/* Candle body */}
            <Bar dataKey="body" stackId="candle" isAnimationActive={false} shape={(props) => {
              const { x, y, width, height, payload } = props
              if (!payload) return null
              return (
                <g>
                  {/* Wick */}
                  <line
                    x1={x + width / 2} y1={props.background?.y + props.background?.height * (1 - (payload.high - priceMin) / (priceMax - priceMin))}
                    x2={x + width / 2} y2={props.background?.y + props.background?.height * (1 - (payload.low - priceMin) / (priceMax - priceMin))}
                    stroke={payload.color}
                    strokeWidth={1}
                  />
                  {/* Body */}
                  <rect
                    x={x + 1}
                    y={y}
                    width={Math.max(width - 2, 2)}
                    height={Math.max(height, 1)}
                    fill={payload.isUp ? payload.color : payload.color}
                    fillOpacity={payload.isUp ? 0.2 : 0.8}
                    stroke={payload.color}
                    strokeWidth={0.5}
                    rx={1}
                  />
                </g>
              )
            }} />
          </ComposedChart>
        </ResponsiveContainer>

        {/* Volume */}
        <ResponsiveContainer width="100%" height="25%">
          <ComposedChart data={chartData} margin={{ top: 0, right: 5, bottom: 5, left: 5 }}>
            <XAxis dataKey="timeLabel" hide />
            <YAxis hide />
            <Bar dataKey="volume" isAnimationActive={false} shape={(props) => {
              const { x, y, width, height, payload } = props
              return (
                <rect
                  x={x + 1}
                  y={y}
                  width={Math.max(width - 2, 2)}
                  height={height}
                  fill={payload?.isUp ? '#22c55e' : '#ef4444'}
                  fillOpacity={0.3}
                  rx={1}
                />
              )
            }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
