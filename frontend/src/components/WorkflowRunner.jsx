import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Play, Upload, FolderOpen, Settings, ChevronDown,
  ChevronUp, CheckCircle2, XCircle, Loader2, Info
} from 'lucide-react'
import { workflowApi } from '../api/client'

const PROFILES    = ['docker', 'singularity', 'standard', 'test', 'simulate_failure']
const PIPELINE_TYPES = ['rnaseq', 'wes', 'custom']

function Field({ label, help, children }) {
  return (
    <div className="space-y-1">
      <label className="block text-xs font-medium text-slate-300">{label}</label>
      {children}
      {help && <p className="text-xs text-slate-500">{help}</p>}
    </div>
  )
}

function Input({ ...props }) {
  return (
    <input
      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2
                 text-sm text-slate-100 placeholder-slate-600 focus:outline-none
                 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50"
      {...props}
    />
  )
}

function Select({ options, ...props }) {
  return (
    <select
      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2
                 text-sm text-slate-100 focus:outline-none focus:border-blue-500"
      {...props}
    >
      {options.map((o) => (
        <option key={o} value={o}>{o}</option>
      ))}
    </select>
  )
}

export default function WorkflowRunner() {
  const navigate = useNavigate()
  const fileInputRef = useRef(null)

  const [form, setForm] = useState({
    name:          '',
    pipeline_type: 'rnaseq',
    profile:       'docker',
    project_name:  '',
    owner:         '',
    description:   '',
    reads:         '',
    genome:        '',
    gtf:           '',
    star_index:    '',
  })

  const [showAdvanced, setShowAdvanced] = useState(false)
  const [uploading, setUploading]       = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadedFiles, setUploadedFiles]   = useState([])
  const [submitting, setSubmitting]     = useState(false)
  const [error, setError]               = useState(null)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files)
    if (!files.length) return
    setUploading(true)
    const uploaded = []
    for (const file of files) {
      try {
        const fd = new FormData()
        fd.append('file', file)
        fd.append('project', form.project_name || 'default')
        const { data } = await workflowApi.uploadFile(fd, setUploadProgress)
        uploaded.push(data)
      } catch (err) {
        setError(`Upload failed for ${file.name}: ${err.message}`)
      }
    }
    setUploadedFiles((prev) => [...prev, ...uploaded])
    setUploading(false)
    setUploadProgress(0)
    // Auto-fill reads field with first fastq path
    const fastq = uploaded.find((f) => f.filename.includes('.fastq') || f.filename.includes('.fq'))
    if (fastq && !form.reads) {
      const dir = fastq.path.replace(/\/[^/]+$/, '')
      setForm((f) => ({ ...f, reads: `${dir}/*_{1,2}.fastq.gz` }))
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) { setError('Pipeline name is required'); return }
    setError(null)
    setSubmitting(true)
    try {
      const payload = {
        name:          form.name.trim(),
        pipeline_type: form.pipeline_type,
        profile:       form.profile,
        project_name:  form.project_name || undefined,
        owner:         form.owner || 'anonymous',
        description:   form.description || undefined,
        reads:         form.reads    || undefined,
        genome:        form.genome   || undefined,
        gtf:           form.gtf      || undefined,
        star_index:    form.star_index || undefined,
      }
      const { data } = await workflowApi.start(payload)
      navigate(`/workflows/${data.workflow_id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Run Pipeline</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Configure and launch a Nextflow bioinformatics workflow
        </p>
      </div>

      {error && (
        <div className="card border-red-700/50 bg-red-950/20 flex items-center gap-2 text-red-400 text-sm">
          <XCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* ── Basic Settings ───────────────────────────────────────────── */}
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Settings className="w-4 h-4 text-blue-400" />
            Pipeline Configuration
          </h2>

          <Field label="Run Name *" help="A descriptive name for this pipeline run">
            <Input
              value={form.name}
              onChange={set('name')}
              placeholder="e.g. RNA-Seq_HepG2_Treatment_2026-03"
              required
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Pipeline Type">
              <Select options={PIPELINE_TYPES} value={form.pipeline_type} onChange={set('pipeline_type')} />
            </Field>
            <Field label="Execution Profile">
              <Select options={PROFILES} value={form.profile} onChange={set('profile')} />
            </Field>
          </div>

          {form.profile === 'simulate_failure' && (
            <div className="flex items-start gap-2 p-3 bg-yellow-950/30 border border-yellow-700/50
                            rounded-lg text-xs text-yellow-300">
              <Info className="w-3 h-3 flex-shrink-0 mt-0.5" />
              <span>
                <strong>simulate_failure</strong> profile sets an invalid STAR index path to
                intentionally trigger a pipeline failure and demonstrate AI troubleshooting.
              </span>
            </div>
          )}
        </div>

        {/* ── File Upload ──────────────────────────────────────────────── */}
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Upload className="w-4 h-4 text-blue-400" />
            Input Files
          </h2>

          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-slate-700 hover:border-blue-600/50
                       rounded-lg p-8 text-center cursor-pointer transition-colors"
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".fastq,.fastq.gz,.fq,.fq.gz,.fa,.fasta,.gtf"
              onChange={handleFileUpload}
              className="hidden"
            />
            {uploading ? (
              <div className="space-y-2">
                <Loader2 className="w-6 h-6 text-blue-400 animate-spin mx-auto" />
                <div className="text-sm text-slate-400">Uploading... {uploadProgress}%</div>
                <div className="w-full bg-slate-700 rounded-full h-1">
                  <div
                    className="bg-blue-500 h-1 rounded-full transition-all"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            ) : (
              <>
                <FolderOpen className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <div className="text-sm text-slate-400">
                  Drop FASTQ files here or <span className="text-blue-400">click to browse</span>
                </div>
                <div className="text-xs text-slate-600 mt-1">
                  .fastq.gz, .fq.gz, .fa, .gtf accepted
                </div>
              </>
            )}
          </div>

          {uploadedFiles.length > 0 && (
            <div className="space-y-1">
              {uploadedFiles.map((f) => (
                <div key={f.path} className="flex items-center gap-2 text-xs text-green-400 bg-green-950/20 px-3 py-1.5 rounded">
                  <CheckCircle2 className="w-3 h-3" />
                  <span className="font-mono">{f.filename}</span>
                  <span className="text-slate-500 ml-auto">{(f.size_bytes / 1e6).toFixed(1)} MB</span>
                </div>
              ))}
            </div>
          )}

          <Field label="Reads Path" help="Glob pattern or directory path to FASTQ files">
            <Input
              value={form.reads}
              onChange={set('reads')}
              placeholder="/data/fastq/*_{1,2}.fastq.gz"
            />
          </Field>
        </div>

        {/* ── Reference Files ──────────────────────────────────────────── */}
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-blue-400" />
            Reference Files
          </h2>
          <Field label="STAR Index" help="Path to pre-built STAR genome index (recommended)">
            <Input value={form.star_index} onChange={set('star_index')} placeholder="/ref/star_index" />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Genome FASTA" help="Required if no STAR index">
              <Input value={form.genome} onChange={set('genome')} placeholder="/ref/genome.fa" />
            </Field>
            <Field label="GTF Annotation">
              <Input value={form.gtf} onChange={set('gtf')} placeholder="/ref/genes.gtf" />
            </Field>
          </div>
        </div>

        {/* ── Advanced Settings ────────────────────────────────────────── */}
        <div className="card">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full flex items-center justify-between text-sm font-semibold text-slate-300"
          >
            <span>Advanced Settings</span>
            {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {showAdvanced && (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Field label="Project Name">
                  <Input value={form.project_name} onChange={set('project_name')} placeholder="My Project" />
                </Field>
                <Field label="Owner">
                  <Input value={form.owner} onChange={set('owner')} placeholder="username" />
                </Field>
              </div>
              <Field label="Description">
                <textarea
                  value={form.description}
                  onChange={set('description')}
                  placeholder="Optional description for this run..."
                  rows={3}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2
                             text-sm text-slate-100 placeholder-slate-600 focus:outline-none
                             focus:border-blue-500 resize-none"
                />
              </Field>
            </div>
          )}
        </div>

        {/* ── Submit ───────────────────────────────────────────────────── */}
        <button type="submit" disabled={submitting} className="btn-primary w-full flex items-center justify-center gap-2 py-3">
          {submitting ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Launching Pipeline...</>
          ) : (
            <><Play className="w-4 h-4" /> Launch Pipeline</>
          )}
        </button>
      </form>
    </div>
  )
}
