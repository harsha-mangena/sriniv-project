import { useState } from 'react'
import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import {
  LayoutDashboard, AlertTriangle, Clock, Settings,
  Shield, ChevronLeft, ChevronRight, Activity
} from 'lucide-react'
import Dashboard from './components/Dashboard'
import AlertsPage from './components/AlertsPage'
import ReplayPage from './components/ReplayPage'
import SettingsPage from './components/SettingsPage'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/alerts', icon: AlertTriangle, label: 'Alerts' },
  { to: '/replay', icon: Clock, label: 'Replay' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function App() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden" style={{ backgroundColor: '#0f1117' }}>
      {/* Sidebar */}
      <aside
        className={`flex flex-col border-r transition-all duration-200 shrink-0 ${collapsed ? 'w-16' : 'w-52'}`}
        style={{ borderColor: '#2d3548', backgroundColor: '#0d1017' }}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-4 border-b" style={{ borderColor: '#2d3548' }}>
          <div className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0" style={{ backgroundColor: '#22d3ee15' }}>
            <Shield className="w-4 h-4 text-cyan-400" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <div className="text-sm font-bold truncate" style={{ color: '#e2e8f0' }}>Surveillance</div>
              <div className="text-[10px] truncate" style={{ color: '#64748b' }}>Market Monitor</div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 py-3 px-2 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  isActive
                    ? 'text-cyan-400'
                    : 'hover:bg-white/5'
                }`
              }
              style={({ isActive }) => ({
                backgroundColor: isActive ? 'rgba(34,211,238,0.08)' : 'transparent',
                color: isActive ? '#22d3ee' : '#94a3b8',
              })}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Status */}
        <div className="px-3 py-3 border-t" style={{ borderColor: '#2d3548' }}>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse-dot shrink-0" />
            {!collapsed && (
              <span className="text-[10px]" style={{ color: '#64748b' }}>System Online</span>
            )}
          </div>
          {!collapsed && (
            <div className="flex items-center gap-1 mt-1.5">
              <Activity className="w-3 h-3" style={{ color: '#64748b' }} />
              <span className="text-[10px] font-mono" style={{ color: '#64748b' }}>
                v1.0.0
              </span>
            </div>
          )}
        </div>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center py-2 border-t hover:bg-white/5 transition-colors"
          style={{ borderColor: '#2d3548', color: '#64748b' }}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header
          className="flex items-center justify-between px-4 py-2.5 border-b shrink-0"
          style={{ borderColor: '#2d3548', backgroundColor: '#0d1017' }}
        >
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>
              Market Manipulation Surveillance
            </h2>
            <span className="px-2 py-0.5 text-[10px] rounded-full font-medium" style={{ backgroundColor: '#22c55e15', color: '#22c55e', border: '1px solid #22c55e30' }}>
              LIVE
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs" style={{ color: '#64748b' }}>
            <span className="font-mono">{new Date().toLocaleTimeString()}</span>
          </div>
        </header>

        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/replay" element={<ReplayPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  )
}
