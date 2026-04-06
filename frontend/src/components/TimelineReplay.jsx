import { useState, useEffect, useRef, useMemo } from 'react'
import { format, subMinutes } from 'date-fns'
import { Play, Pause, SkipBack, SkipForward, FastForward, RotateCcw, Clock } from 'lucide-react'
import { generateAlerts } from '../data/mockData'

const speeds = [0.5, 1, 2, 5, 10]

const severityColors = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#64748b',
}

export default function TimelineReplay() {
  const [events] = useState(() => generateAlerts(60).map((a, i) => ({
    ...a,
    timeOffset: i * 120 + Math.random() * 60, // seconds from start
  })).sort((a, b) => a.timeOffset - b.timeOffset))

  const totalDuration = Math.max(...events.map(e => e.timeOffset), 1)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [speed, setSpeed] = useState(1)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        setCurrentTime(prev => {
          const next = prev + speed * 0.1
          if (next >= totalDuration) {
            setPlaying(false)
            return totalDuration
          }
          return next
        })
      }, 100)
    }
    return () => clearInterval(intervalRef.current)
  }, [playing, speed, totalDuration])

  const visibleEvents = useMemo(
    () => events.filter(e => e.timeOffset <= currentTime),
    [events, currentTime]
  )

  const progress = (currentTime / totalDuration) * 100

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const pct = x / rect.width
    setCurrentTime(pct * totalDuration)
  }

  const cycleSpeed = () => {
    const idx = speeds.indexOf(speed)
    setSpeed(speeds[(idx + 1) % speeds.length])
  }

  return (
    <div className="rounded-lg border p-4" style={{ borderColor: '#2d3548', backgroundColor: '#161b22' }}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>Timeline Replay</h3>
          <span className="text-xs" style={{ color: '#64748b' }}>
            {visibleEvents.length} / {events.length} events
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Clock className="w-3.5 h-3.5" style={{ color: '#64748b' }} />
          <span className="text-xs font-mono" style={{ color: '#94a3b8' }}>
            {formatTime(currentTime)} / {formatTime(totalDuration)}
          </span>
        </div>
      </div>

      {/* Timeline track */}
      <div
        className="relative h-16 rounded-lg cursor-pointer mb-3 overflow-hidden"
        style={{ backgroundColor: '#0f1117', border: '1px solid #2d3548' }}
        onClick={handleSeek}
      >
        {/* Progress fill */}
        <div
          className="absolute inset-y-0 left-0 opacity-10"
          style={{ width: `${progress}%`, backgroundColor: '#22d3ee' }}
        />

        {/* Event dots */}
        {events.map((event, i) => {
          const x = (event.timeOffset / totalDuration) * 100
          const y = event.severity === 'critical' ? 15
            : event.severity === 'high' ? 30
            : event.severity === 'medium' ? 45
            : 55
          const isVisible = event.timeOffset <= currentTime
          const isSelected = selectedEvent?.id === event.id

          return (
            <div
              key={event.id}
              className="absolute cursor-pointer transition-all"
              style={{
                left: `${x}%`,
                top: y,
                transform: 'translate(-50%, -50%)',
                zIndex: isSelected ? 10 : 1,
              }}
              onClick={(e) => {
                e.stopPropagation()
                setSelectedEvent(event)
              }}
            >
              <div
                className={`rounded-full transition-all ${isSelected ? 'ring-2 ring-cyan-400' : ''}`}
                style={{
                  width: isSelected ? 10 : event.severity === 'critical' ? 8 : 6,
                  height: isSelected ? 10 : event.severity === 'critical' ? 8 : 6,
                  backgroundColor: severityColors[event.severity],
                  opacity: isVisible ? 1 : 0.2,
                  boxShadow: isVisible && event.severity === 'critical' ? `0 0 6px ${severityColors[event.severity]}` : 'none',
                }}
              />
            </div>
          )
        })}

        {/* Playhead */}
        <div
          className="absolute top-0 bottom-0 w-0.5"
          style={{
            left: `${progress}%`,
            backgroundColor: '#22d3ee',
            boxShadow: '0 0 6px rgba(34,211,238,0.5)',
          }}
        />

        {/* Severity labels */}
        <div className="absolute right-2 top-0 bottom-0 flex flex-col justify-between py-1.5 text-[8px]" style={{ color: '#64748b' }}>
          <span>CRIT</span>
          <span>HIGH</span>
          <span>MED</span>
          <span>LOW</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => { setCurrentTime(0); setPlaying(false) }}
            className="p-1.5 rounded-md hover:bg-white/5 transition-colors" style={{ color: '#94a3b8' }}
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setCurrentTime(Math.max(0, currentTime - 30))}
            className="p-1.5 rounded-md hover:bg-white/5 transition-colors" style={{ color: '#94a3b8' }}
          >
            <SkipBack className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setPlaying(!playing)}
            className="p-2 rounded-lg transition-colors"
            style={{ backgroundColor: '#22d3ee20', color: '#22d3ee', border: '1px solid #22d3ee40' }}
          >
            {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>
          <button
            onClick={() => setCurrentTime(Math.min(totalDuration, currentTime + 30))}
            className="p-1.5 rounded-md hover:bg-white/5 transition-colors" style={{ color: '#94a3b8' }}
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={cycleSpeed}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-mono transition-colors hover:bg-white/5"
            style={{ color: '#94a3b8', border: '1px solid #2d3548' }}
          >
            <FastForward className="w-3 h-3" />
            {speed}x
          </button>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 text-[10px]">
          {Object.entries(severityColors).map(([sev, color]) => (
            <div key={sev} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              <span style={{ color: '#64748b' }}>{sev}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Selected event detail */}
      {selectedEvent && (
        <div className="mt-3 p-3 rounded-lg animate-fade-in" style={{ backgroundColor: '#1c2333', border: '1px solid #2d3548' }}>
          <div className="flex items-center gap-2 mb-1">
            <span
              className="text-[10px] px-1.5 py-0.5 rounded font-bold uppercase"
              style={{ backgroundColor: severityColors[selectedEvent.severity] + '20', color: severityColors[selectedEvent.severity] }}
            >
              {selectedEvent.severity}
            </span>
            <span className="text-xs font-semibold" style={{ color: '#e2e8f0' }}>
              {selectedEvent.alert_type?.replace(/_/g, ' ')}
            </span>
            <span className="text-xs font-mono" style={{ color: '#64748b' }}>{selectedEvent.symbol}</span>
            <span className="ml-auto text-xs font-mono" style={{ color: '#64748b' }}>
              T+{formatTime(selectedEvent.timeOffset)}
            </span>
          </div>
          <p className="text-[11px] line-clamp-2" style={{ color: '#94a3b8' }}>
            {selectedEvent.explanation}
          </p>
        </div>
      )}
    </div>
  )
}
