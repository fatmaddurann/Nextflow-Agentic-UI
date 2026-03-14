import { useState, useEffect, useRef } from 'react'
import { Terminal, Download, Search } from 'lucide-react'

const LEVEL_STYLES = {
  error:    'log-error',
  critical: 'log-error',
  warning:  'log-warning',
  warn:     'log-warning',
  info:     'log-info',
  debug:    'log-info text-slate-600',
  failure_detected: 'log-error border-red-600 bg-red-950/50 font-semibold',
}

function formatLine(line) {
  if (!line) return ''
  // Strip ISO timestamps that are very long
  return line.replace(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?\s*/, '')
}

export default function LogViewer({ historicalLogs = [], liveLines = [], isRunning }) {
  const [search, setSearch]       = useState('')
  const [levelFilter, setLevel]   = useState('all')
  const [autoScroll, setAutoScroll] = useState(true)
  const bottomRef = useRef(null)
  const containerRef = useRef(null)

  // Merge historical + live, deduplicated
  const allLines = [
    ...historicalLogs.map((l) => ({
      id:      l.id,
      level:   l.level || 'info',
      message: l.raw_line || l.message,
      ts:      l.timestamp,
      process: l.process,
    })),
    ...liveLines.map((l, i) => ({
      id:      `live-${i}`,
      level:   l.level || (l.type === 'failure_detected' ? 'error' : 'info'),
      message: l.line || l.message || JSON.stringify(l),
      ts:      l.timestamp,
      process: l.process || null,
      live:    true,
      type:    l.type,
    })),
  ]

  // Filter
  const filtered = allLines.filter((l) => {
    if (levelFilter !== 'all' && l.level !== levelFilter) return false
    if (search && !l.message?.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [filtered.length, autoScroll])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
    setAutoScroll(atBottom)
  }

  const downloadLogs = () => {
    const text = allLines.map((l) => `[${l.level?.toUpperCase()}] ${l.message}`).join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = 'pipeline.log'; a.click()
    URL.revokeObjectURL(url)
  }

  const LEVELS = ['all', 'info', 'warning', 'error']

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search logs..."
            className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-2
                       text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500"
          />
        </div>
        <div className="flex gap-1">
          {LEVELS.map((l) => (
            <button
              key={l}
              onClick={() => setLevel(l)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                levelFilter === l
                  ? l === 'error'   ? 'bg-red-600 text-white'
                  : l === 'warning' ? 'bg-yellow-600 text-white'
                  : 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              {l}
            </button>
          ))}
        </div>
        <button onClick={downloadLogs} className="btn-ghost flex items-center gap-1.5 py-1 px-3 text-xs">
          <Download className="w-3 h-3" /> Export
        </button>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>{filtered.length} lines</span>
          {isRunning && (
            <label className="flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="rounded"
              />
              Auto-scroll
            </label>
          )}
        </div>
      </div>

      {/* Log container */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="bg-slate-950 border border-slate-800 rounded-xl overflow-auto font-mono"
        style={{ height: '480px' }}
      >
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-700 text-sm gap-2">
            <Terminal className="w-6 h-6" />
            {isRunning ? 'Waiting for log output...' : 'No logs match your filter'}
          </div>
        ) : (
          <div className="py-2">
            {filtered.map((line) => (
              <div key={line.id} className={LEVEL_STYLES[line.level] || 'log-info'}>
                <span className="text-slate-700 mr-2 text-[10px] select-none">
                  {line.process ? `[${line.process}]` : ''}
                </span>
                <span className="break-all">{formatLine(line.message)}</span>
                {line.type === 'failure_detected' && (
                  <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] bg-red-600 text-white">
                    FAILURE DETECTED
                  </span>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
    </div>
  )
}
