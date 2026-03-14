import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts'
import {
  Activity, CheckCircle2, XCircle, Clock, Play,
  TrendingUp, Zap, AlertTriangle
} from 'lucide-react'
import { workflowApi } from '../api/client'
import { formatDistance } from 'date-fns'

const STATUS_COLORS = {
  completed: '#22c55e',
  running:   '#3b82f6',
  failed:    '#ef4444',
  pending:   '#94a3b8',
  cancelled: '#f59e0b',
}

const STATUS_ICONS = {
  completed: <CheckCircle2 className="w-4 h-4 text-green-400" />,
  running:   <Activity     className="w-4 h-4 text-blue-400 animate-pulse" />,
  failed:    <XCircle      className="w-4 h-4 text-red-400" />,
  pending:   <Clock        className="w-4 h-4 text-slate-400" />,
  cancelled: <AlertTriangle className="w-4 h-4 text-yellow-400" />,
}

function StatCard({ icon, label, value, sub, color }) {
  return (
    <div className="card flex items-start gap-4">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
        {icon}
      </div>
      <div>
        <div className="text-2xl font-bold text-white">{value}</div>
        <div className="text-sm font-medium text-slate-300">{label}</div>
        {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    const fetch = async () => {
      try {
        const { data } = await workflowApi.dashboard()
        setSummary(data)
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    fetch()
    const interval = setInterval(fetch, 10_000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-500">
      <Activity className="w-6 h-6 animate-spin mr-2" />
      <span>Loading dashboard...</span>
    </div>
  )

  if (error) return (
    <div className="card border-red-700/50 bg-red-950/20">
      <div className="flex items-center gap-2 text-red-400">
        <XCircle className="w-5 h-5" />
        <span>Failed to load dashboard: {error}</span>
      </div>
    </div>
  )

  const counts = summary?.status_counts || {}
  const chartData = Object.entries(counts).map(([status, count]) => ({ status, count }))

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">Pipeline execution overview</p>
        </div>
        <Link to="/run" className="btn-primary flex items-center gap-2">
          <Play className="w-4 h-4" />
          New Run
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<TrendingUp className="w-5 h-5 text-white" />}
          label="Total Runs"
          value={summary?.total_runs || 0}
          color="bg-blue-600/20 border border-blue-700/50"
        />
        <StatCard
          icon={<CheckCircle2 className="w-5 h-5 text-white" />}
          label="Completed"
          value={counts.completed || 0}
          color="bg-green-600/20 border border-green-700/50"
        />
        <StatCard
          icon={<Activity className="w-5 h-5 text-white" />}
          label="Running"
          value={counts.running || 0}
          sub="Currently active"
          color="bg-purple-600/20 border border-purple-700/50"
        />
        <StatCard
          icon={<XCircle className="w-5 h-5 text-white" />}
          label="Failed"
          value={counts.failed || 0}
          sub="AI analysis available"
          color="bg-red-600/20 border border-red-700/50"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status chart */}
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <BarChart className="w-4 h-4 text-blue-400" size={16}/>
            Runs by Status
          </h2>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={chartData} barSize={40}>
                <XAxis dataKey="status" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                  cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry) => (
                    <Cell key={entry.status} fill={STATUS_COLORS[entry.status] || '#64748b'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[180px] text-slate-600 text-sm">
              No data yet
            </div>
          )}
        </div>

        {/* Recent workflows */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-400" />
              Recent Runs
            </h2>
            <Link to="/workflows" className="text-xs text-blue-400 hover:text-blue-300">
              View all →
            </Link>
          </div>
          <div className="space-y-2">
            {(summary?.recent_workflows || []).map((wf) => (
              <Link
                key={wf.workflow_id}
                to={`/workflows/${wf.workflow_id}`}
                className="flex items-center justify-between p-2 rounded-lg
                           hover:bg-slate-700/50 transition-colors group"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {STATUS_ICONS[wf.status] || <Clock className="w-4 h-4 text-slate-500" />}
                  <div className="min-w-0">
                    <div className="text-sm text-slate-200 truncate">{wf.name}</div>
                    <div className="text-xs text-slate-500">
                      {wf.created_at ? formatDistance(new Date(wf.created_at), new Date(), { addSuffix: true }) : '—'}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                  <span className={`status-${wf.status}`}>{wf.status}</span>
                  {wf.duration && (
                    <span className="text-xs text-slate-500">
                      {Math.round(wf.duration / 60)}m
                    </span>
                  )}
                </div>
              </Link>
            ))}
            {(!summary?.recent_workflows || summary.recent_workflows.length === 0) && (
              <div className="text-center py-8 text-slate-600 text-sm">
                No workflows yet.{' '}
                <Link to="/run" className="text-blue-400 hover:underline">Start your first run →</Link>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick tips */}
      <div className="card border-blue-700/30 bg-blue-950/20">
        <div className="flex items-start gap-3">
          <Zap className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-medium text-blue-300">AI-Powered Troubleshooting</div>
            <div className="text-xs text-slate-400 mt-1">
              When a pipeline fails, the AI agent automatically analyses logs and retrieves
              relevant solutions from the knowledge base — no manual debugging required.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
