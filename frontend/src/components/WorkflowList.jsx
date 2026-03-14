import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  List, Activity, CheckCircle2, XCircle, Clock,
  AlertTriangle, RefreshCw, ChevronRight, Filter
} from 'lucide-react'
import { workflowApi } from '../api/client'
import { formatDistance } from 'date-fns'

const STATUS_STYLES = {
  running:   'status-running',
  completed: 'status-completed',
  failed:    'status-failed',
  pending:   'status-pending',
  cancelled: 'status-cancelled',
}

const STATUS_ICONS = {
  running:   <Activity      className="w-3.5 h-3.5 animate-pulse" />,
  completed: <CheckCircle2  className="w-3.5 h-3.5" />,
  failed:    <XCircle       className="w-3.5 h-3.5" />,
  pending:   <Clock         className="w-3.5 h-3.5" />,
  cancelled: <AlertTriangle className="w-3.5 h-3.5" />,
}

const FILTERS = ['all', 'running', 'completed', 'failed', 'pending', 'cancelled']

export default function WorkflowList() {
  const [workflows, setWorkflows] = useState([])
  const [filter, setFilter]       = useState('all')
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [page, setPage]           = useState(1)
  const [total, setTotal]         = useState(0)

  const PAGE_SIZE = 20

  const load = async () => {
    try {
      setLoading(true)
      const params = { page, page_size: PAGE_SIZE }
      if (filter !== 'all') params.status = filter
      const { data } = await workflowApi.list(params)
      setWorkflows(data.items)
      setTotal(data.total)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filter, page])

  // Auto-refresh for running workflows
  useEffect(() => {
    const interval = setInterval(() => {
      if (workflows.some((w) => w.status === 'running')) load()
    }, 5000)
    return () => clearInterval(interval)
  }, [workflows])

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <List className="w-5 h-5 text-blue-400" />
            Workflows
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">{total} total runs</p>
        </div>
        <button onClick={load} disabled={loading} className="btn-ghost flex items-center gap-2">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2">
        <Filter className="w-3 h-3 text-slate-500" />
        <div className="flex gap-1 flex-wrap">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => { setFilter(f); setPage(1) }}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                filter === f
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="card border-red-700/50 bg-red-950/20 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-left">
              <th className="px-4 py-3 text-xs font-medium text-slate-500">Name</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-500">Status</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-500">Type</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-500">Started</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-500">Duration</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-500">Owner</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {workflows.map((wf) => (
              <tr key={wf.workflow_id} className="hover:bg-slate-800/50 transition-colors group">
                <td className="px-4 py-3">
                  <div className="text-slate-200 font-medium truncate max-w-[200px]">{wf.name}</div>
                  <div className="text-xs text-slate-600 font-mono">{wf.workflow_id}</div>
                  {wf.failed_process && (
                    <div className="text-xs text-red-400 mt-0.5">↳ Failed: {wf.failed_process}</div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={STATUS_STYLES[wf.status] || 'status-pending'}>
                    {STATUS_ICONS[wf.status]}
                    {wf.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs uppercase">{wf.pipeline_type}</td>
                <td className="px-4 py-3 text-slate-500 text-xs">
                  {wf.created_at
                    ? formatDistance(new Date(wf.created_at), new Date(), { addSuffix: true })
                    : '—'}
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs">
                  {wf.duration_seconds ? `${Math.round(wf.duration_seconds / 60)}m` : '—'}
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs">{wf.owner || '—'}</td>
                <td className="px-4 py-3">
                  <Link
                    to={`/workflows/${wf.workflow_id}`}
                    className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300
                               opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    View <ChevronRight className="w-3 h-3" />
                  </Link>
                </td>
              </tr>
            ))}

            {!loading && workflows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-slate-600 text-sm">
                  No workflows found. <Link to="/run" className="text-blue-400 hover:underline">Start a run →</Link>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}</span>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="btn-ghost px-3 py-1 text-xs disabled:opacity-50"
            >
              Previous
            </button>
            <button
              disabled={page * PAGE_SIZE >= total}
              onClick={() => setPage((p) => p + 1)}
              className="btn-ghost px-3 py-1 text-xs disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
