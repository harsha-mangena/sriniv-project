import { useState } from 'react'
import { Save, RefreshCw, Bell, Monitor, Database, Wifi } from 'lucide-react'

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    apiUrl: 'http://localhost:8000',
    wsUrl: 'ws://localhost:8000',
    defaultSymbols: 'BTCUSDT, ETHUSDT',
    alertSoundEnabled: true,
    autoScroll: true,
    darkMode: true,
    refreshInterval: 5,
    maxAlerts: 100,
    confidenceThreshold: 30,
    enabledDetectors: {
      spoofing: true,
      wash_trading: true,
      layering: true,
      quote_stuffing: true,
      intent_mismatch: true,
    },
  })

  const update = (key, value) => setSettings(prev => ({ ...prev, [key]: value }))
  const toggleDetector = (key) => setSettings(prev => ({
    ...prev,
    enabledDetectors: { ...prev.enabledDetectors, [key]: !prev.enabledDetectors[key] },
  }))

  const inputClass = "w-full px-3 py-2 text-sm rounded-md border focus:outline-none focus:border-cyan-500"
  const inputStyle = { backgroundColor: '#1c2333', borderColor: '#2d3548', color: '#e2e8f0' }

  return (
    <div className="flex-1 overflow-y-auto p-4 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-bold mb-1" style={{ color: '#e2e8f0' }}>Settings</h1>
        <p className="text-xs" style={{ color: '#64748b' }}>Configure the surveillance platform</p>
      </div>

      <div className="space-y-6">
        {/* Connection */}
        <section className="rounded-lg border p-4" style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: '#e2e8f0' }}>
            <Wifi className="w-4 h-4 text-cyan-400" />
            Connection
          </h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs block mb-1" style={{ color: '#94a3b8' }}>API Base URL</label>
              <input
                type="text"
                value={settings.apiUrl}
                onChange={e => update('apiUrl', e.target.value)}
                className={inputClass}
                style={inputStyle}
              />
            </div>
            <div>
              <label className="text-xs block mb-1" style={{ color: '#94a3b8' }}>WebSocket URL</label>
              <input
                type="text"
                value={settings.wsUrl}
                onChange={e => update('wsUrl', e.target.value)}
                className={inputClass}
                style={inputStyle}
              />
            </div>
            <div>
              <label className="text-xs block mb-1" style={{ color: '#94a3b8' }}>Default Symbols</label>
              <input
                type="text"
                value={settings.defaultSymbols}
                onChange={e => update('defaultSymbols', e.target.value)}
                className={inputClass}
                style={inputStyle}
              />
            </div>
          </div>
        </section>

        {/* Display */}
        <section className="rounded-lg border p-4" style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: '#e2e8f0' }}>
            <Monitor className="w-4 h-4 text-blue-400" />
            Display
          </h2>
          <div className="space-y-3">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-xs" style={{ color: '#94a3b8' }}>Auto-scroll trade stream</span>
              <button
                onClick={() => update('autoScroll', !settings.autoScroll)}
                className={`w-9 h-5 rounded-full transition-colors ${settings.autoScroll ? 'bg-cyan-500' : 'bg-gray-600'}`}
              >
                <div className={`w-4 h-4 rounded-full bg-white transition-transform ${settings.autoScroll ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
              </button>
            </label>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: '#94a3b8' }}>Refresh interval (seconds)</span>
              <input
                type="number"
                min="1"
                max="60"
                value={settings.refreshInterval}
                onChange={e => update('refreshInterval', Number(e.target.value))}
                className="w-20 px-2 py-1 text-xs text-center rounded border"
                style={inputStyle}
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: '#94a3b8' }}>Max alerts displayed</span>
              <input
                type="number"
                min="10"
                max="500"
                value={settings.maxAlerts}
                onChange={e => update('maxAlerts', Number(e.target.value))}
                className="w-20 px-2 py-1 text-xs text-center rounded border"
                style={inputStyle}
              />
            </div>
          </div>
        </section>

        {/* Alerts */}
        <section className="rounded-lg border p-4" style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: '#e2e8f0' }}>
            <Bell className="w-4 h-4 text-yellow-400" />
            Alert Settings
          </h2>
          <div className="space-y-3">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-xs" style={{ color: '#94a3b8' }}>Sound notifications</span>
              <button
                onClick={() => update('alertSoundEnabled', !settings.alertSoundEnabled)}
                className={`w-9 h-5 rounded-full transition-colors ${settings.alertSoundEnabled ? 'bg-cyan-500' : 'bg-gray-600'}`}
              >
                <div className={`w-4 h-4 rounded-full bg-white transition-transform ${settings.alertSoundEnabled ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
              </button>
            </label>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: '#94a3b8' }}>Min confidence threshold</span>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={settings.confidenceThreshold}
                  onChange={e => update('confidenceThreshold', Number(e.target.value))}
                  className="w-24 accent-cyan-400"
                />
                <span className="text-xs font-mono w-8" style={{ color: '#e2e8f0' }}>{settings.confidenceThreshold}%</span>
              </div>
            </div>
          </div>
        </section>

        {/* Detectors */}
        <section className="rounded-lg border p-4" style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: '#e2e8f0' }}>
            <Database className="w-4 h-4 text-purple-400" />
            Enabled Detectors
          </h2>
          <div className="space-y-2">
            {Object.entries(settings.enabledDetectors).map(([key, enabled]) => (
              <label key={key} className="flex items-center justify-between cursor-pointer py-1">
                <span className="text-xs capitalize" style={{ color: '#94a3b8' }}>
                  {key.replace(/_/g, ' ')}
                </span>
                <button
                  onClick={() => toggleDetector(key)}
                  className={`w-9 h-5 rounded-full transition-colors ${enabled ? 'bg-cyan-500' : 'bg-gray-600'}`}
                >
                  <div className={`w-4 h-4 rounded-full bg-white transition-transform ${enabled ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
                </button>
              </label>
            ))}
          </div>
        </section>

        {/* Save button */}
        <button
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style={{ backgroundColor: '#22d3ee20', color: '#22d3ee', border: '1px solid #22d3ee40' }}
        >
          <Save className="w-4 h-4" />
          Save Settings
        </button>
      </div>
    </div>
  )
}
