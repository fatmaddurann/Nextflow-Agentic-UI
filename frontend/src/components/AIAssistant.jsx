import { useState } from 'react'
import {
  Zap, AlertTriangle, Lightbulb, BookOpen,
  ChevronDown, ChevronUp, Loader2, RefreshCw,
  CheckCircle2, XCircle, Target
} from 'lucide-react'

function ConfidenceBar({ value }) {
  const pct   = Math.round((value || 0) * 100)
  const color = pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-700 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-400 w-8 text-right">{pct}%</span>
    </div>
  )
}

function Section({ icon, title, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-slate-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-800/50 hover:bg-slate-800 transition-colors"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
          {icon}
          {title}
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
      </button>
      {open && <div className="px-4 py-3 bg-slate-900/50">{children}</div>}
    </div>
  )
}

export default function AIAssistant({ analysis, workflowStatus, onTrigger }) {
  const [triggering, setTriggering] = useState(false)

  const handleTrigger = async () => {
    setTriggering(true)
    await onTrigger?.()
    setTriggering(false)
  }

  // No analysis yet
  if (!analysis) {
    return (
      <div className="space-y-4">
        <div className="card border-dashed text-center py-10 space-y-4">
          <div className="w-12 h-12 bg-slate-800 rounded-full flex items-center justify-center mx-auto">
            <Zap className="w-6 h-6 text-slate-600" />
          </div>
          <div>
            <div className="text-sm font-medium text-slate-300">No AI Analysis Yet</div>
            <div className="text-xs text-slate-500 mt-1">
              {workflowStatus === 'failed'
                ? 'The AI agent will analyse this failure automatically, or trigger it manually.'
                : 'AI analysis runs automatically when a pipeline failure is detected.'}
            </div>
          </div>
          {(workflowStatus === 'failed' || workflowStatus === 'completed') && (
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="btn-primary mx-auto flex items-center gap-2 text-sm"
            >
              {triggering
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Analysing...</>
                : <><Zap className="w-4 h-4" /> Run AI Analysis</>
              }
            </button>
          )}
        </div>

        {/* How it works */}
        <div className="card border-blue-700/30 bg-blue-950/20 text-xs text-slate-400 space-y-2">
          <div className="font-medium text-blue-300 flex items-center gap-2">
            <Lightbulb className="w-3.5 h-3.5" />
            How AI Troubleshooting Works
          </div>
          <div className="space-y-1">
            {[
              '1. Collects pipeline logs and failed process metadata',
              '2. Retrieves matching error patterns from the knowledge base (RAG)',
              '3. Sends context to GPT-4o for root cause analysis',
              '4. Returns prioritised, actionable troubleshooting steps',
            ].map((s) => <div key={s}>{s}</div>)}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg
                          flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white">AI Analysis</div>
            {analysis.model_used && (
              <div className="text-xs text-slate-500">{analysis.model_used}</div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div>
            <div className="text-xs text-slate-500 mb-1">Confidence</div>
            <ConfidenceBar value={analysis.confidence} />
          </div>
          <button onClick={handleTrigger} disabled={triggering} className="btn-ghost p-2">
            <RefreshCw className={`w-3.5 h-3.5 ${triggering ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Error summary */}
      <div className="bg-red-950/30 border border-red-700/50 rounded-xl p-4">
        <div className="flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-medium text-red-300 mb-1">Error Summary</div>
            <div className="text-sm text-slate-300">{analysis.error_summary}</div>
          </div>
        </div>
      </div>

      {/* Root cause */}
      {analysis.root_cause && (
        <Section icon={<Target className="w-4 h-4 text-orange-400" />} title="Root Cause">
          <p className="text-sm text-slate-300 leading-relaxed">{analysis.root_cause}</p>
        </Section>
      )}

      {/* Affected steps */}
      {analysis.affected_steps?.length > 0 && (
        <Section icon={<XCircle className="w-4 h-4 text-red-400" />} title="Affected Pipeline Steps">
          <div className="flex flex-wrap gap-2">
            {analysis.affected_steps.map((s) => (
              <span key={s} className="px-2.5 py-1 bg-red-950/50 border border-red-700/50
                                       text-red-300 rounded-lg text-xs font-mono">
                {s}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* Suggestions */}
      {analysis.suggestions?.length > 0 && (
        <Section icon={<Lightbulb className="w-4 h-4 text-yellow-400" />} title="Troubleshooting Steps">
          <ol className="space-y-3">
            {analysis.suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-3">
                <div className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-600/20 border border-blue-700/50
                                flex items-center justify-center text-[10px] text-blue-400 font-bold">
                  {i + 1}
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">{s}</p>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {/* RAG sources */}
      {analysis.rag_sources?.length > 0 && (
        <Section
          icon={<BookOpen className="w-4 h-4 text-purple-400" />}
          title="Knowledge Base Sources"
          defaultOpen={false}
        >
          <div className="space-y-2">
            {analysis.rag_sources.map((src) => (
              <div key={src.doc_id} className="flex items-center justify-between p-2
                                               bg-slate-800/50 rounded-lg text-xs">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3 h-3 text-purple-400" />
                  <span className="text-slate-300">{src.title}</span>
                </div>
                <span className="text-slate-500">
                  {Math.round((src.relevance || 0) * 100)}% match
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Metadata */}
      {analysis.tokens_used > 0 && (
        <div className="text-xs text-slate-600 text-right">
          {analysis.tokens_used} tokens used · {analysis.model_used || 'GPT-4o'}
        </div>
      )}
    </div>
  )
}
