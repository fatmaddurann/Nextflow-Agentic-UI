# AI Troubleshooting Demo — Example Pipeline Failure & Agent Response

This document demonstrates the end-to-end AI troubleshooting workflow using the
`simulate_failure` Nextflow profile, which deliberately triggers a STAR index error.

---

## 1. Triggering a Pipeline Failure

### API Call — Start pipeline with simulate_failure profile
```bash
curl -X POST http://localhost:8000/api/v1/workflows/ \
  -H "Content-Type: application/json" \
  -d '{
    "name":          "RNA-Seq Demo (Simulate Failure)",
    "pipeline_type": "rnaseq",
    "profile":       "simulate_failure",
    "owner":         "demo_user",
    "reads":         "/data/test/*_{1,2}.fastq.gz",
    "gtf":           "/ref/genes.gtf"
  }'
```

### Response
```json
{
  "workflow_id": "wf-a3b4c5d6e7f8",
  "name": "RNA-Seq Demo (Simulate Failure)",
  "status": "pending",
  "pipeline_type": "rnaseq",
  "profile": "simulate_failure",
  "created_at": "2026-03-15T10:00:00.000Z"
}
```

---

## 2. Real-Time Log Stream (WebSocket)

Connect to the live log stream:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/wf-a3b4c5d6e7f8')
ws.onmessage = (e) => console.log(JSON.parse(e.data))
```

### Log output captured during failure

```
[INFO ] Launching `main.nf` [jolly_rutherford] DSL2 - revision: abc123
[INFO ] executor >  local (1)
[INFO ] [d3/f1a2b3] process > FASTQC (sample1)           [  0%] 0 of 1
[INFO ] [d3/f1a2b3] process > TRIMMOMATIC (sample1)      [  0%] 0 of 1
[INFO ] [d3/f1a2b3] process > FASTQC (sample1)           [100%] 1 of 1 ✔
[INFO ] [e5/c6d7e8] process > TRIMMOMATIC (sample1)      [100%] 1 of 1 ✔
[INFO ] [ab/123456] process > STAR_ALIGN (sample1)       [  0%] 0 of 1

[ERROR] Error executing process > 'STAR_ALIGN (sample1)'

Caused by:
  Process `STAR_ALIGN (sample1)` terminated with an error exit status (1)

Command executed:
  STAR \
    --runMode alignReads \
    --runThreadN 8 \
    --genomeDir /nonexistent/star_index \   ← intentional failure
    --readFilesIn sample1_paired_1.fastq.gz sample1_paired_2.fastq.gz \
    ...

Command exit status:
  1

Command output:
  EXITING because of FATAL ERROR: could not open genome files.
  Genome file does not exist: /nonexistent/star_index/Genome
  TIP: If you are running --runMode alignReads, make sure --genomeDir points to a
       valid STAR genome index directory generated with --runMode genomeGenerate.

Work dir:
  /pipeline/work/ab/123456789abc

[INFO ] Tip: view the complete command output by changing to the process work dir
             and entering the command: `cat .command.out`
```

### WebSocket failure event emitted
```json
{
  "type":        "failure_detected",
  "workflow_id": "wf-a3b4c5d6e7f8",
  "category":    "star_index_missing",
  "severity":    "critical",
  "hint":        "STAR genome index is missing or corrupt. Regenerate with STAR_GENOMEGENERATE.",
  "line":        "EXITING because of FATAL ERROR: could not open genome files."
}
```

---

## 3. Automatic AI Analysis Triggered

The `LogMonitor` detects the failure pattern and calls `on_pipeline_failure()`,
which invokes the LangGraph agent graph:

```
Node 1: collect_logs     → fetches 47 log lines from DB, identifies 3 ERROR lines
Node 2: retrieve_rag     → embeds query, retrieves top-5 KB articles
Node 3: analyze_failure  → calls GPT-4o with logs + RAG context
Node 4: persist_results  → saves AIAnalysis to database
Node 5: broadcast_results → pushes result to WebSocket
```

### RAG Retrieval Query
```
Pipeline: rnaseq
Failed process: STAR_ALIGN
Error logs: EXITING because of FATAL ERROR: could not open genome files.
Genome file does not exist: /nonexistent/star_index/Genome
```

### Top-3 Retrieved Knowledge Base Articles
| Rank | Article | Relevance |
|------|---------|-----------|
| 1 | STAR: Genome Index Not Found (genomeDir) | 94% |
| 2 | STAR: Insufficient Memory for Alignment  | 61% |
| 3 | Docker: Container Image Pull Failed      | 43% |

---

## 4. AI Analysis Response

### GET /api/v1/workflows/wf-a3b4c5d6e7f8/analysis

```json
{
  "id": 1,
  "workflow_id": "wf-a3b4c5d6e7f8",
  "created_at": "2026-03-15T10:02:14.000Z",
  "error_summary": "The STAR_ALIGN process failed because the genome index directory '/nonexistent/star_index' does not exist. STAR cannot perform alignment without a pre-built genome index.",
  "root_cause": "The --star_index parameter was set to '/nonexistent/star_index' (an intentionally invalid path in the simulate_failure profile). STAR attempted to load the genome index files (Genome, SA, SAindex) from this directory but found none, causing an immediate fatal exit.",
  "affected_steps": ["STAR_ALIGN"],
  "suggestions": [
    "Step 1: Verify the STAR index path exists — run: ls -la /your/star_index/ and confirm Genome, SA, and SAindex files are present.",
    "Step 2: If no index exists, build one by running the pipeline WITHOUT --star_index but WITH --genome and --gtf: nextflow run main.nf --genome /ref/hg38.fa --gtf /ref/genes.gtf",
    "Step 3: Alternatively, download a pre-built STAR index for your genome from AWS iGenomes: aws s3 cp s3://ngi-igenomes/igenomes/Homo_sapiens/NCBI/GRCh38/Sequence/STARIndex/ /ref/star_index/ --recursive --no-sign-request",
    "Step 4: Ensure the Docker volume mount includes the star_index directory. Add to docker-compose.yml: volumes: - /host/path/star_index:/ref/star_index",
    "Step 5: If the index exists but is from a different STAR version, rebuild it. STAR indices are not compatible across major versions.",
    "Step 6: After fixing the path, resume the pipeline to skip completed steps: nextflow run main.nf -resume --star_index /correct/path"
  ],
  "rag_sources": [
    {
      "doc_id":   "star-001",
      "title":    "STAR: Genome Index Not Found (genomeDir)",
      "relevance": 0.94
    },
    {
      "doc_id":   "star-002",
      "title":    "STAR: genomeSAindexNbases Too Large",
      "relevance": 0.61
    }
  ],
  "confidence": 0.95,
  "model_used": "gpt-4o",
  "tokens_used": 1247
}
```

---

## 5. WebSocket AI Analysis Broadcast

```json
{
  "type":           "ai_analysis_complete",
  "workflow_id":    "wf-a3b4c5d6e7f8",
  "timestamp":      "2026-03-15T10:02:14.000Z",
  "error_summary":  "STAR_ALIGN failed: genome index not found at /nonexistent/star_index",
  "root_cause":     "The --star_index parameter points to a non-existent directory...",
  "affected_steps": ["STAR_ALIGN"],
  "suggestions": [
    "Step 1: Verify the STAR index path exists...",
    "Step 2: Build the index with --genome and --gtf...",
    "Step 3: Download a pre-built index from AWS iGenomes...",
    "Step 4: Check Docker volume mounts...",
    "Step 5: Rebuild if using wrong STAR version...",
    "Step 6: Resume pipeline after fixing the path..."
  ],
  "confidence": 0.95,
  "rag_sources": [
    { "doc_id": "star-001", "title": "STAR: Genome Index Not Found", "relevance": 0.94 }
  ]
}
```

---

## 6. Pipeline Resume After Fix

```bash
# Fix: provide correct star_index path
curl -X POST http://localhost:8000/api/v1/workflows/wf-a3b4c5d6e7f8/resume
```

Nextflow's `-resume` flag reuses cached work from FASTQC and TRIMMOMATIC,
only re-running STAR_ALIGN and downstream steps.

```
[INFO ] Resuming workflow from cache...
[INFO ] [d3/f1a2b3] process > FASTQC (sample1)      [100%] 1 of 1, cached ✔
[INFO ] [e5/c6d7e8] process > TRIMMOMATIC (sample1) [100%] 1 of 1, cached ✔
[INFO ] [ab/123456] process > STAR_ALIGN (sample1)  [100%] 1 of 1 ✔    ← re-run
[INFO ] [cd/789abc] process > SAMTOOLS_SORT         [100%] 1 of 1 ✔
[INFO ] [ef/012345] process > SAMTOOLS_INDEX        [100%] 1 of 1 ✔
[INFO ] [gh/678901] process > FEATURECOUNTS         [100%] 1 of 1 ✔
[INFO ] [ij/234567] process > MULTIQC               [100%] 1 of 1 ✔
[INFO ] Pipeline completed successfully in 43m 12s
```

---

## 7. Other Supported Failure Scenarios

| Failure Type | Exit Code | Pattern Detected | Category |
|---|---|---|---|
| STAR index missing | 1 | `FATAL ERROR.*genomeDir` | `star_index_missing` |
| OOM / out of memory | 137 | `OOMKilled\|Cannot allocate memory` | `out_of_memory` |
| Docker pull failed | 1 | `Unable to find image` | `docker_pull_failed` |
| Corrupt FASTQ | 1 | `SequenceFormatException` | `fastqc_error` |
| Missing adapter file | 1 | `ILLUMINACLIP.*Error` | `trimmomatic_adapter` |
| GTF mismatch | 1 | `featureCounts.*failed` | `featurecounts_gtf_error` |
| Missing parameter | 1 | `Missing required.*param` | `missing_param` |
| Disk full | 1 | `No space left on device` | `disk_full` |

Each pattern triggers the AI agent with an appropriate category hint,
which focuses the RAG retrieval and prompts the LLM toward the correct knowledge domain.
