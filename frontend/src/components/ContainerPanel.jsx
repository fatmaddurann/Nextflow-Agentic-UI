import { useState, useEffect } from 'react'
import {
  Container, RefreshCw, Square, RotateCcw,
  Trash2, Activity, Terminal
} from 'lucide-react'
import { containerApi } from '../api/client'

const STATE_BADGE = {
  running:    'bg-green-900/50 text-green-300 border-green-700',
  exited:     'bg-slate-700/50 text-slate-400 border-slate-600',
  paused:     'bg-yellow-900/50 text-yellow-300 border-yellow-700',
  created:    'bg-blue-900/50 text-blue-300 border-blue-700',
  restarting: 'bg-purple-900/50 text-purple-300 border-purple-700',
}

export default function ContainerPanel() {
  const [containers, setContainers] = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [logs, setLogs]             = useState(null)
  const [logsLoading, setLogsLoading] = useState(false)

  const load = async () => {
    try {
      setLoading(true)
      const { data } = await containerApi.list({ all: true })
      setContainers(data)
      setError(null)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const iv = setInterval(load, 8000)
    return () => clearInterval(iv)
  }, [])

  const viewLogs = async (id) => {
    setSelectedId(id)
    setLogsLoading(true)
    try {
      const { data } = await containerApi.getLogs(id, 200)
      setLogs(data.logs)
    } catch (e) { setLogs('Failed to fetch logs') }
    finally { setLogsLoading(false) }
  }

  const cleanup = async () => {
    await containerApi.cleanup()
    load()
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Container className="w-5 h-5 text-blue-400" />
            Containers
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">{containers.length} containers</p>
        </div>
        <div className="flex gap-2">
          <button onClick={cleanup} className="btn-ghost flex items-center gap-2 text-sm">
            <Trash2 className="w-3.5 h-3.5" /> Prune Exited
          </button>
          <button onClick={load} disabled={loading} className="btn-ghost flex items-center gap-2 text-sm">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && <div className="card border-red-700/50 bg-red-950/20 text-red-400 text-sm">{error}</div>}

      <div className="grid gap-3">
        {containers.map((c) => (
          <div key={c.container_id} className="card hover:border-slate-600 transition-colors">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-slate-200 truncate">{c.name}</span>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs border
                                   ${STATE_BADGE[c.state] || STATE_BADGE.exited}`}>
                    {c.state === 'running' && <Activity className="w-2.5 h-2.5 mr-1 animate-pulse" />}
                    {c.state}
                  </span>
                  {c.exit_code !== null && c.exit_code !== undefined && (
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      c.exit_code === 0 ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                    }`}>
                      exit {c.exit_code}
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-500 font-mono mt-1 truncate">{c.image}</div>
                <div className="text-xs text-slate-600 font-mono">{c.container_id}</div>
                {c.workflow_id && (
                  <div className="text-xs text-blue-400 mt-0.5">workflow: {c.workflow_id}</div>
                )}
              </div>

              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  onClick={() => viewLogs(c.container_id)}
                  className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
                  title="View logs"
                >
                  <Terminal className="w-3.5 h-3.5" />
                </button>
                {c.state === 'running' && (
                  <button
                    onClick={async () => { await containerApi.stop(c.container_id); load() }}
                    className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-red-400 transition-colors"
                    title="Stop"
                  >
                    <Square className="w-3.5 h-3.5" />
                  </button>
                )}
                {c.state === 'exited' && (
                  <button
                    onClick={async () => { await containerApi.restart(c.container_id); load() }}
                    className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-blue-400 transition-colors"
                    title="Restart"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        {!loading && containers.length === 0 && (
          <div className="card text-center py-12 text-slate-600 text-sm">
            No containers found. Containers appear here when a pipeline is running.
          </div>
        )}
      </div>

      {/* Logs drawer */}
      {selectedId && (
        <div className="card border-slate-600">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-slate-300 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-blue-400" />
              Container Logs: <span className="font-mono text-xs">{selectedId}</span>
            </h3>
            <button onClick={() => setSelectedId(null)} className="text-xs text-slate-500 hover:text-slate-300">
              Close ×
            </button>
          </div>
          <pre className="bg-slate-950 rounded-lg p-3 text-xs font-mono text-slate-300 overflow-auto max-h-80 whitespace-pre-wrap">
            {logsLoading ? 'Loading...' : logs || 'No logs'}
          </pre>
        </div>
      )}
    </div>
  )
}
