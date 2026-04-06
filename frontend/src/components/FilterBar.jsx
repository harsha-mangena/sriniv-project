import { useState } from 'react'
import { Search, Filter, X, ChevronDown } from 'lucide-react'

const alertTypes = [
  { value: '', label: 'All Types' },
  { value: 'spoofing', label: 'Spoofing' },
  { value: 'wash_trading', label: 'Wash Trading' },
  { value: 'layering', label: 'Layering' },
  { value: 'quote_stuffing', label: 'Quote Stuffing' },
  { value: 'intent_mismatch', label: 'Intent Mismatch' },
]

const severityOptions = [
  { value: '', label: 'All Severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

const symbols = ['', 'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'XRPUSDT']

export default function FilterBar({ filters = {}, onFilterChange, onClear }) {
  const [expanded, setExpanded] = useState(false)

  const update = (key, value) => {
    onFilterChange?.({ ...filters, [key]: value })
  }

  const hasFilters = Object.values(filters).some(v => v !== '' && v != null)

  const selectClass = "bg-bg-tertiary border border-border text-text-primary text-xs rounded-md px-2.5 py-1.5 focus:outline-none focus:border-accent-cyan appearance-none cursor-pointer"

  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-3" style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search */}
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" style={{ color: '#64748b' }} />
          <input
            type="text"
            placeholder="Search alerts..."
            value={filters.search || ''}
            onChange={e => update('search', e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-bg-tertiary border border-border text-text-primary text-xs rounded-md placeholder-text-muted focus:outline-none focus:border-accent-cyan"
            style={{ backgroundColor: '#1c2333', borderColor: '#2d3548', color: '#e2e8f0' }}
          />
        </div>

        {/* Symbol */}
        <select
          value={filters.symbol || ''}
          onChange={e => update('symbol', e.target.value)}
          className={selectClass}
          style={{ backgroundColor: '#1c2333', borderColor: '#2d3548' }}
        >
          <option value="">All Assets</option>
          {symbols.filter(Boolean).map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        {/* Alert Type */}
        <select
          value={filters.alert_type || ''}
          onChange={e => update('alert_type', e.target.value)}
          className={selectClass}
          style={{ backgroundColor: '#1c2333', borderColor: '#2d3548' }}
        >
          {alertTypes.map(t => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        {/* Severity */}
        <select
          value={filters.severity || ''}
          onChange={e => update('severity', e.target.value)}
          className={selectClass}
          style={{ backgroundColor: '#1c2333', borderColor: '#2d3548' }}
        >
          {severityOptions.map(s => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>

        {/* Expand/Collapse */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors"
          style={{ color: '#64748b' }}
        >
          <Filter className="w-3.5 h-3.5" />
          <ChevronDown className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </button>

        {/* Clear */}
        {hasFilters && (
          <button
            onClick={onClear}
            className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 transition-colors"
          >
            <X className="w-3 h-3" />
            Clear
          </button>
        )}
      </div>

      {/* Expanded filters */}
      {expanded && (
        <div className="mt-3 pt-3 border-t flex items-center gap-4 flex-wrap" style={{ borderColor: '#2d3548' }}>
          {/* Confidence Range */}
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: '#64748b' }}>Confidence:</span>
            <input
              type="range"
              min="0"
              max="100"
              value={filters.min_confidence || 0}
              onChange={e => update('min_confidence', Number(e.target.value))}
              className="w-24 h-1 bg-border rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
            <span className="text-xs font-mono" style={{ color: '#94a3b8' }}>
              {filters.min_confidence || 0}%+
            </span>
          </div>

          {/* Time Range */}
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: '#64748b' }}>Time:</span>
            {['1h', '6h', '24h', '7d'].map(range => (
              <button
                key={range}
                onClick={() => update('time_range', filters.time_range === range ? '' : range)}
                className={`px-2 py-0.5 text-xs rounded border transition-colors ${
                  filters.time_range === range
                    ? 'border-cyan-500 text-cyan-400 bg-cyan-500/10'
                    : 'border-border text-text-muted hover:text-text-primary'
                }`}
                style={filters.time_range !== range ? { borderColor: '#2d3548', color: '#64748b' } : {}}
              >
                {range}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
