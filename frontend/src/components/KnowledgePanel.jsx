import { useState } from 'react'
import { BookOpen, Search, Tag, ChevronDown, ChevronUp } from 'lucide-react'

// Import the raw knowledge base articles for local display
const CATEGORIES = {
  star_errors:         { label: 'STAR Alignment',  color: 'bg-blue-900/30 text-blue-300 border-blue-700/50' },
  fastqc_errors:       { label: 'FastQC',           color: 'bg-green-900/30 text-green-300 border-green-700/50' },
  docker_errors:       { label: 'Docker',           color: 'bg-orange-900/30 text-orange-300 border-orange-700/50' },
  trimmomatic_errors:  { label: 'Trimmomatic',      color: 'bg-purple-900/30 text-purple-300 border-purple-700/50' },
  featurecounts_errors:{ label: 'featureCounts',    color: 'bg-pink-900/30 text-pink-300 border-pink-700/50' },
  nextflow_errors:     { label: 'Nextflow DSL2',    color: 'bg-cyan-900/30 text-cyan-300 border-cyan-700/50' },
  memory_errors:       { label: 'Memory / OOM',     color: 'bg-red-900/30 text-red-300 border-red-700/50' },
  disk_errors:         { label: 'Disk Space',       color: 'bg-yellow-900/30 text-yellow-300 border-yellow-700/50' },
}

const ARTICLES = [
  { id: 'star-001', title: 'STAR: Genome Index Not Found', category: 'star_errors',
    tags: ['STAR','alignment','index'],
    summary: 'STAR fails when --star_index points to a missing or empty directory.',
    content: `STAR fails with "EXITING because of FATAL ERROR: could not open genome files".

Cause: The STAR genome index directory is missing, empty, or its path is incorrect.

Solution:
1. Verify the star_index path: ls -la /path/to/star_index/
2. Check for required files: Genome, SA, SAindex, chrName.txt
3. Rebuild the index: nextflow run main.nf --genome genome.fa --gtf genes.gtf
4. If using Docker, ensure the volume mount includes the index directory`
  },
  { id: 'star-002', title: 'STAR: genomeSAindexNbases Too Large', category: 'star_errors',
    tags: ['STAR','small genome','genomeSAindexNbases'],
    summary: 'For small genomes, genomeSAindexNbases must be reduced from the default 14.',
    content: `Formula: min(14, floor(log2(GenomeLength)/2 - 1))

python3 -c "import math; print(min(14, int(math.log2(3e9)/2 - 1)))"

Pass to pipeline: --extra_params '{"genomeSAindexNbases": "11"}'`
  },
  { id: 'docker-003', title: 'Docker: OOMKilled (Exit 137)', category: 'docker_errors',
    tags: ['Docker','OOM','memory','exit 137'],
    summary: 'Exit code 137 = container killed by OS due to memory limit exceeded.',
    content: `Exit code 137 = 128 + 9 (SIGKILL from OOM killer).

Solution:
1. Increase memory in nextflow.config:
   withName: STAR_ALIGN { memory = '64.GB' }
2. Use auto-retry with escalating memory:
   errorStrategy = 'retry'; maxRetries = 3
   memory = { check_max(8.GB * task.attempt, 'memory') }`
  },
  { id: 'fastqc-001', title: 'FastQC: Invalid or Corrupt FASTQ', category: 'fastqc_errors',
    tags: ['FastQC','FASTQ','corrupt','input'],
    summary: 'FastQC fails with Java exceptions when the input FASTQ is corrupt or truncated.',
    content: `Verify file integrity:
gzip -t sample_R1.fastq.gz
zcat sample_R1.fastq.gz | head -8  # line 1 starts with @, line 3 is +`
  },
  { id: 'nextflow-001', title: 'Nextflow: Missing Required Parameter', category: 'nextflow_errors',
    tags: ['Nextflow','params','missing'],
    summary: 'Pipeline fails when required parameters like --reads, --genome, or --gtf are not provided.',
    content: `Minimum required params for RNA-Seq:
nextflow run main.nf \\
  --reads '/data/*.fastq.gz' \\
  --star_index /ref/star_index  # OR --genome + --gtf`
  },
  { id: 'memory-001', title: 'Out of Memory — Process Killed', category: 'memory_errors',
    tags: ['OOM','memory','RAM','killed'],
    summary: 'Memory-hungry tools (STAR, BWA) are killed when insufficient RAM is allocated.',
    content: `Memory heuristics:
- STAR alignment:   30-40 GB (human genome)
- BWA MEM:          5-10 GB
- featureCounts:    2-8 GB
- Samtools sort:    scales with -m flag

errorStrategy = { task.exitStatus == 137 ? 'retry' : 'finish' }
memory = { check_max(8.GB * task.attempt, 'memory') }`
  },
  { id: 'disk-001', title: 'Disk Space Exhausted', category: 'disk_errors',
    tags: ['disk','storage','space'],
    summary: 'Pipeline fails with "No space left on device" — typical RNA-Seq generates 100 GB+ intermediates.',
    content: `Check disk usage: df -h && du -sh /pipeline/work
Clean previous runs: nextflow clean -f
Prune Docker: docker container prune

Space estimate: input size × 10-20× for intermediates`
  },
  { id: 'featurecounts-001', title: 'featureCounts: GTF Mismatch', category: 'featurecounts_errors',
    tags: ['featureCounts','GTF','chromosome','annotation'],
    summary: 'featureCounts assigns 0 reads when BAM and GTF use different chromosome naming conventions.',
    content: `Check chromosome naming:
samtools view -H sample.bam | grep @SQ | head
head -100 genes.gtf | cut -f1 | sort -u

Fix: sed 's/^chr//' genes.gtf > genes_nochr.gtf  # remove chr prefix`
  },
]

function ArticleCard({ article }) {
  const [expanded, setExpanded] = useState(false)
  const cat = CATEGORIES[article.category] || { label: article.category, color: 'bg-slate-700/50 text-slate-300 border-slate-600' }

  return (
    <div className="card hover:border-slate-600 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h3 className="text-sm font-medium text-white">{article.title}</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full border ${cat.color}`}>
              {cat.label}
            </span>
          </div>
          <p className="text-xs text-slate-400">{article.summary}</p>
          <div className="flex gap-1 mt-2 flex-wrap">
            {article.tags.map((t) => (
              <span key={t} className="flex items-center gap-0.5 text-xs text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded">
                <Tag className="w-2.5 h-2.5" />{t}
              </span>
            ))}
          </div>
        </div>
        <button onClick={() => setExpanded(!expanded)} className="flex-shrink-0 text-slate-500 hover:text-slate-300">
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>
      {expanded && (
        <pre className="mt-3 bg-slate-950 rounded-lg p-3 text-xs text-slate-300 font-mono overflow-auto whitespace-pre-wrap border-t border-slate-700 pt-3">
          {article.content}
        </pre>
      )}
    </div>
  )
}

export default function KnowledgePanel() {
  const [search, setSearch] = useState('')
  const [catFilter, setCatFilter] = useState('all')

  const filtered = ARTICLES.filter((a) => {
    if (catFilter !== 'all' && a.category !== catFilter) return false
    if (search) {
      const q = search.toLowerCase()
      return a.title.toLowerCase().includes(q) ||
             a.summary.toLowerCase().includes(q) ||
             a.tags.some((t) => t.toLowerCase().includes(q))
    }
    return true
  })

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-blue-400" />
          Knowledge Base
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {ARTICLES.length} curated troubleshooting articles — used by the AI agent for RAG retrieval
        </p>
      </div>

      {/* Search and filter */}
      <div className="flex gap-3 items-center flex-wrap">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search articles..."
            className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-xs
                       text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          <button
            onClick={() => setCatFilter('all')}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              catFilter === 'all' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            }`}
          >
            All
          </button>
          {Object.entries(CATEGORIES).map(([key, { label }]) => (
            <button
              key={key}
              onClick={() => setCatFilter(key)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                catFilter === key ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Articles */}
      <div className="space-y-3">
        {filtered.map((a) => <ArticleCard key={a.id} article={a} />)}
        {filtered.length === 0 && (
          <div className="card text-center py-8 text-slate-600 text-sm">
            No articles match your search.
          </div>
        )}
      </div>
    </div>
  )
}
