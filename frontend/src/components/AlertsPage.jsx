import { useState, useMemo } from 'react'
import FilterBar from './FilterBar'
import AlertsFeed from './AlertsFeed'
import EventDetail from './EventDetail'
import { generateAlerts } from '../data/mockData'

export default function AlertsPage() {
  const [alerts] = useState(() => generateAlerts(50))
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [filters, setFilters] = useState({})

  const filtered = useMemo(() => {
    return alerts.filter(a => {
      if (filters.symbol && a.symbol !== filters.symbol) return false
      if (filters.alert_type && a.alert_type !== filters.alert_type) return false
      if (filters.severity && a.severity !== filters.severity) return false
      if (filters.min_confidence && a.confidence_score < filters.min_confidence) return false
      if (filters.search) {
        const q = filters.search.toLowerCase()
        if (!a.explanation.toLowerCase().includes(q) && !a.symbol.toLowerCase().includes(q) && !a.alert_type.toLowerCase().includes(q)) return false
      }
      return true
    })
  }, [alerts, filters])

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <div>
        <h1 className="text-xl font-bold mb-1" style={{ color: '#e2e8f0' }}>Alerts</h1>
        <p className="text-xs" style={{ color: '#64748b' }}>
          {filtered.length} of {alerts.length} alerts matching filters
        </p>
      </div>

      <FilterBar
        filters={filters}
        onFilterChange={setFilters}
        onClear={() => setFilters({})}
      />

      <AlertsFeed
        onSelectAlert={setSelectedAlert}
        limit={50}
      />

      {selectedAlert && (
        <EventDetail alert={selectedAlert} onClose={() => setSelectedAlert(null)} />
      )}
    </div>
  )
}
