import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Activity, CheckCircle2, XCircle, Clock,
  Square, RotateCcw, Zap,
  AlertTriangle, Terminal, RefreshCw
} from 'lucide-react'
import { workflowApi, logApi, createWebSocket } from '../api/client'
import AIAssistant from './AIAssistant'
import LogViewer from './LogViewer'

export default function WorkflowDetail() {
  const { id }  = useParams()
  const [wf, setWf]             = useState(null)
  const [logs, setLogs]         = useState([])
  const [analysis, setAnalysis] = useState(null)
  const [liveLines, setLiveLines] = useState([])
  const [wsStatus, setWsStatus] = useState('disconnected') // connecting|connected|disconnected
  const [activeTab, setActiveTab] = useState('logs')
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const wsRef = useRef(null)

  const loadWorkflow = useCallback(async () => {
    try {
      const { data } = await workflowApi.get(id)
      setWf(data)
    } catch (e) { setError(e.message) }
  }, [id])

  const loadLogs = useCallback(async () => {
    try {
      const { data } = await logApi.getLogs(id, { page_size: 500 })
      setLogs(data.items)
    } catch (_e) { /* non-critical, silently ignore */ }
  }, [id])

  const loadAnalysis = useCallback(async () => {
    try {
      const { data } = await workflowApi.getAnalysis(id)
      setAnalysis(data)
    } catch (_e) { /* non-critical, silently ignore */ }
  }, [id])

  // Connect WebSocket for live streaming
  useEffect(() => {
    setWsStatus('connecting')
    const ws = createWebSocket(id, {
      onOpen:         () => setWsStatus('connected'),
      onClose:        () => setWsStatus('disconnected'),
      onError:        () => setWsStatus('error'),
      onLogLine:      (d) => setLiveLines((prev) => [...prev.slice(-999), d]),
      onFailure:      (d) => setLiveLines((prev) => [...prev, { ...d, type: 'failure_detected' }]),
      onAIAnalysis:   (d) => setAnalysis(d),
      onStatusUpdate: (d) => setWf((prev) => prev ? { ...prev, status: d.status } : prev),
    })
    wsRef.current = ws
    return () => ws.closeWithCleanup?.()
  }, [id])

  // Initial data load
  useEffect(() => {
    const init = async () => {
      setLoading(true)
      await Promise.all([loadWorkflow(), loadLogs(), loadAnalysis()])
      setLoading(false)
    }
    init()
  }, [id])

  // Poll status for running workflows
  useEffect(() => {
    if (!wf || wf.status !== 'running') return
    const interval = setInterval(loadWorkflow, 5000)
    return () => clearInterval(interval)
  }, [wf?.status])

  const handleStop = async () => {
    await workflowApi.stop(id)
    await loadWorkflow()
  }

  const handleResume = async () => {
    await workflowApi.resume(id)
  }

  const handleTriggerAI = async () => {
    await workflowApi.triggerAnalysis(id)
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-500">
      <Activity className="w-5 h-5 animate-spin mr-2" /> Loading workflow...
    </div>
  )
  if (error || !wf) return (
    <div className="card border-red-700/50 bg-red-950/20 text-red-400">
      {error || 'Workflow not found'}
    </div>
  )

  const statusIcon = {
    running:   <Activity      className="w-5 h-5 text-blue-400 animate-pulse" />,
    completed: <CheckCircle2  className="w-5 h-5 text-green-400" />,
    failed:    <XCircle       className="w-5 h-5 text-red-400" />,
    pending:   <Clock         className="w-5 h-5 text-slate-400" />,
    cancelled: <AlertTriangle className="w-5 h-5 text-yellow-400" />,
  }[wf.status]

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link to="/workflows" className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 mb-2">
            <ArrowLeft className="w-3 h-3" /> Back to workflows
          </Link>
          <div className="flex items-center gap-3">
            {statusIcon}
            <h1 className="text-xl font-bold text-white">{wf.name}</h1>
            <span className={`status-${wf.status}`}>{wf.status}</span>
          </div>
          <div className="text-xs text-slate-500 font-mono mt-1">{wf.workflow_id}</div>
        </div>

        <div className="flex items-center gap-2">
          {wf.status === 'running' && (
            <button onClick={handleStop} className="btn-danger flex items-center gap-2 text-sm">
              <Square className="w-3 h-3" /> Stop
            </button>
          )}
          {wf.status === 'failed' && (
            <button onClick={handleResume} className="btn-ghost flex items-center gap-2 text-sm">
              <RotateCcw className="w-3 h-3" /> Resume
            </button>
          )}
          {(wf.status === 'failed' || wf.status === 'completed') && !analysis && (
            <button onClick={handleTriggerAI} className="btn-primary flex items-center gap-2 text-sm">
              <Zap className="w-3 h-3" /> Analyse with AI
            </button>
          )}
          <button onClick={loadWorkflow} className="btn-ghost p-2">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Meta cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Pipeline',  value: wf.pipeline_type?.toUpperCase() },
          { label: 'Profile',   value: wf.profile },
          { label: 'Owner',     value: wf.owner || '—' },
          { label: 'Exit Code', value: wf.exit_code ?? '—', danger: wf.exit_code && wf.exit_code !== 0 },
        ].map(({ label, value, danger }) => (
          <div key={label} className="card py-3">
            <div className="text-xs text-slate-500">{label}</div>
            <div className={`text-sm font-medium mt-0.5 ${danger ? 'text-red-400' : 'text-slate-200'}`}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {wf.failed_process && (
        <div className="card border-red-700/50 bg-red-950/20 flex items-center gap-2 text-sm">
          <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <span className="text-slate-400">Failed at process:</span>
          <span className="text-red-300 font-mono font-medium">{wf.failed_process}</span>
          {wf.error_message && <span className="text-slate-500 text-xs ml-2 truncate">{wf.error_message}</span>}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-700 pb-0">
        {[
          { key: 'logs',   label: 'Logs',        icon: Terminal },
          { key: 'ai',     label: 'AI Analysis', icon: Zap },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t-lg
              transition-colors border-b-2 -mb-px ${
              activeTab === key
                ? 'border-blue-500 text-blue-400 bg-slate-800/50'
                : 'border-transparent text-slate-500 hover:text-slate-300'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
            {key === 'ai' && analysis && (
              <span className="w-2 h-2 rounded-full bg-green-400 ml-0.5" />
            )}
          </button>
        ))}

        {/* WebSocket indicator */}
        <div className="ml-auto flex items-center gap-1.5 text-xs text-slate-500 pb-2 pr-1">
          <div className={`w-1.5 h-1.5 rounded-full ${
            wsStatus === 'connected' ? 'bg-green-400 animate-pulse' :
            wsStatus === 'connecting' ? 'bg-yellow-400 animate-pulse' : 'bg-slate-600'
          }`} />
          {wsStatus}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === 'logs' && (
        <LogViewer
          historicalLogs={logs}
          liveLines={liveLines}
          isRunning={wf.status === 'running'}
        />
      )}

      {activeTab === 'ai' && (
        <AIAssistant
          analysis={analysis}
          workflowId={id}
          workflowStatus={wf.status}
          onTrigger={handleTriggerAI}
        />
      )}
    </div>
  )
}
