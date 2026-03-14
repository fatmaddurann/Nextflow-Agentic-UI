# Nextflow-Agentic-UI — System Architecture

## Overview

Nextflow-Agentic-UI is a production-grade intelligent pipeline management platform
that combines workflow execution, container orchestration, real-time monitoring, and
AI-powered troubleshooting into a single cohesive interface for bioinformaticians.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Nextflow-Agentic-UI System                          │
│                                                                             │
│  ┌─────────────┐   REST/WS   ┌──────────────────┐   subprocess   ┌───────┐ │
│  │  React UI   │◄───────────►│  FastAPI Backend  │──────────────►│  NF   │ │
│  │  (Port 3000)│             │   (Port 8000)     │               │ Pipeline│ │
│  └─────────────┘             └──────────────────┘               └───────┘ │
│         │                           │                                │       │
│         │                    ┌──────┴──────┐            ┌───────────┴──┐    │
│         │                    │  SQLite /   │            │    Docker    │    │
│         │                    │ PostgreSQL  │            │  Containers  │    │
│         │                    └─────────────┘            └──────────────┘    │
│         │                           │                                        │
│         │                    ┌──────┴──────┐            ┌──────────────┐    │
│         └──────── AI ────────►  LangGraph  │◄──────────►  ChromaDB    │    │
│                              │  AI Agent   │            │ (RAG Store)  │    │
│                              └─────────────┘            └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Folder Structure

```
Nextflow-Agentic-UI/
│
├── docker-compose.yml           # Full stack orchestration
├── .env.example                 # Environment configuration template
│
├── pipeline/                    # Nextflow RNA-Seq Pipeline (DSL2)
│   ├── main.nf                  # Main workflow entry point
│   ├── nextflow.config          # Resource profiles, container assignments
│   ├── modules/
│   │   ├── fastqc.nf            # FastQC quality control
│   │   ├── trimmomatic.nf       # Adapter trimming
│   │   ├── star.nf              # STAR genome index + alignment
│   │   ├── samtools.nf          # BAM sort + index
│   │   ├── featurecounts.nf     # Gene quantification
│   │   └── multiqc.nf           # Aggregate QC report
│   ├── data/adapters/           # Trimmomatic adapter files
│   └── test_data/               # Test FASTQ + reference files
│
├── backend/                     # FastAPI Python Backend
│   ├── main.py                  # Application entry point, lifespan hooks
│   ├── Dockerfile               # Multi-stage production image
│   ├── requirements.txt         # Python dependencies
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── workflows.py     # Workflow CRUD + file upload endpoints
│   │   │   ├── logs.py          # Log retrieval + WebSocket streaming
│   │   │   └── containers.py    # Docker SDK container management
│   │   └── models/
│   │       └── schemas.py       # Pydantic v2 request/response schemas
│   │
│   ├── database/
│   │   ├── database.py          # Async SQLAlchemy engine + session factory
│   │   ├── models.py            # ORM models (WorkflowRun, WorkflowLog, AIAnalysis...)
│   │   └── crud.py              # Async CRUD operations
│   │
│   ├── services/
│   │   ├── workflow_manager.py  # Pipeline launch / stop / resume logic
│   │   ├── container_manager.py # Docker SDK integration
│   │   ├── log_monitor.py       # Log tailing, failure detection, WebSocket broadcast
│   │   └── ai_agent.py          # LangGraph agent for failure analysis
│   │
│   └── rag/
│       └── knowledge_base.py    # ChromaDB RAG store + document indexing
│
├── frontend/                    # React + Vite + Tailwind UI
│   ├── Dockerfile               # Build + Nginx serve
│   ├── nginx.conf               # SPA routing + API/WS proxy
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx              # Root + router + sidebar navigation
│       ├── api/client.js        # Axios client + WebSocket factory
│       └── components/
│           ├── Dashboard.jsx    # Overview stats + charts + recent runs
│           ├── WorkflowRunner.jsx # Pipeline launch form + file upload
│           ├── WorkflowList.jsx # Paginated workflow table with filters
│           ├── WorkflowDetail.jsx # Detail view + live log stream + AI tab
│           ├── LogViewer.jsx    # Log display with search + level filter
│           ├── AIAssistant.jsx  # AI analysis results with suggestions
│           ├── ContainerPanel.jsx # Docker container management UI
│           └── KnowledgePanel.jsx # Searchable knowledge base browser
│
├── monitoring/                  # Sidecar monitoring service
│   ├── Dockerfile
│   └── monitor.py               # Polls logs + trace files, reports to API
│
└── docs/
    ├── ARCHITECTURE.md          # This document
    └── AI_TROUBLESHOOTING_DEMO.md # End-to-end failure demo
```

---

## Component Deep-Dives

### 1. Workflow Layer (Nextflow DSL2)

The RNA-Seq pipeline is built with Nextflow DSL2 for full modularity:

```
Input FASTQs
    │
    ▼
┌─────────┐    ┌─────────────┐    ┌────────────┐    ┌──────────────────┐
│ FASTQC  │    │ TRIMMOMATIC │    │    STAR    │    │  FEATURECOUNTS   │
│ (raw QC)│───►│  (trimming) │───►│ (alignment)│───►│ (quantification) │
└─────────┘    └─────────────┘    └────────────┘    └──────────────────┘
                                        │
                               ┌────────┘
                               ▼
                       ┌──────────────┐    ┌──────────────┐
                       │SAMTOOLS_SORT │───►│SAMTOOLS_INDEX│
                       └──────────────┘    └──────────────┘
                                                   │
                   ┌───────────────────────────────┘
                   ▼
               ┌─────────┐
               │ MULTIQC │  ← aggregates all QC reports
               └─────────┘
```

Each module:
- Runs in its own Docker container (biocontainers)
- Declares explicit input/output channels with metadata tuples
- Supports `stub` mode for testing without real data
- Uses `check_max()` helper for HPC-safe resource limits
- Supports automatic retry on exit codes 130-145 (memory/signal kills)

### 2. FastAPI Backend

The backend uses fully async Python (asyncio + SQLAlchemy async ORM):

```
HTTP Request
    │
    ▼
┌──────────────────────────────────────────────────────┐
│                    FastAPI App                        │
│  - CORS middleware                                    │
│  - GZip middleware                                   │
│  - Request logging middleware                        │
│  - Global exception handler                          │
└──────────────────────────────────────────────────────┘
    │
    ├── /api/v1/workflows/  → WorkflowManager.start_pipeline()
    │                          → async subprocess (Nextflow)
    │                          → SQLAlchemy async session
    │
    ├── /api/v1/logs/       → WorkflowLog CRUD
    │   /ws/{workflow_id}   → WebSocket → ws_manager.broadcast()
    │
    └── /api/v1/containers/ → DockerClient (Docker SDK)
```

### 3. Log Monitor

The `LogMonitor` implements a tail-like mechanism using async file polling:

```
LogMonitor._tail_log(workflow_id, log_file)
    │
    ├── Every 3 seconds:
    │   ├── Read new bytes from log file (position tracking)
    │   ├── For each new line:
    │   │   ├── Broadcast to WebSocket clients
    │   │   └── Check against 15+ failure patterns (regex)
    │   │       └── If match:
    │   │           ├── Broadcast failure_detected event
    │   │           └── Call on_pipeline_failure() callback
    │   └── If workflow terminal: stop monitoring
    │
    └── Registered callback: ai_agent.analyze_workflow()
```

### 4. AI Agent (LangGraph)

The agent is a 5-node LangGraph graph that activates on failure:

```
                    AgentState
                        │
              ┌─────────▼──────────┐
              │   collect_logs     │ ← DB query: logs + workflow metadata
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │   retrieve_rag     │ ← ChromaDB cosine similarity search
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │  analyze_failure   │ ← GPT-4o with system prompt + context
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │  persist_results   │ ← Save AIAnalysis to DB
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │ broadcast_results  │ ← WebSocket push to UI
              └─────────┬──────────┘
                        │
                       END
```

**LLM Prompt Strategy:**
- System prompt: expert bioinformatics engineer persona
- Human message: structured context block (metadata + error logs + RAG context)
- Response: forced JSON schema for reliable structured output
- Temperature: 0.1 for consistent, reproducible technical advice

### 5. RAG Knowledge Base

The knowledge base uses ChromaDB with OpenAI embeddings:

```
KNOWLEDGE_BASE (Python list)
    │
    ▼
OpenAIEmbeddings.aembed_documents()   ← text-embedding-3-small
    │
    ▼
ChromaDB.collection.add()             ← cosine similarity index (HNSW)
    │
    ▼ (at query time)
Query string → embed → cosine search → top-K documents → LLM context
```

**Knowledge Base Coverage (15 articles across 8 categories):**
- STAR errors (index, memory, genomeSAindexNbases)
- FastQC errors (corrupt input, read pair mismatch)
- Docker errors (pull failed, permission, OOMKilled)
- Trimmomatic errors (missing adapter file)
- Nextflow errors (missing params, channel mismatch, NFS issues)
- featureCounts errors (GTF mismatch)
- Memory / OOM errors (general guidance)
- Disk space errors

### 6. React Frontend

Key design decisions:
- **Dark terminal aesthetic** — familiar to bioinformaticians
- **Monospace font** — for log readability
- **WebSocket-first** — live log streaming without polling
- **Tailwind CSS** — utility-first, no runtime CSS-in-JS overhead
- **Recharts** — lightweight charts for status overview
- **React Router v6** — client-side routing for SPA navigation

---

## Data Flow

### Successful Pipeline Run
```
User → POST /workflows/ → WorkflowManager → Nextflow subprocess
                                         ↓
                                    Log file written
                                         ↓
                                   LogMonitor tails
                                         ↓
                                WebSocket broadcast → UI
                                         ↓
                              Nextflow exits (0) → DB: COMPLETED
```

### Failed Pipeline Run
```
User → POST /workflows/ → WorkflowManager → Nextflow subprocess
                                         ↓
                               Error log lines detected
                                         ↓
                         LogMonitor: failure pattern matched
                                         ↓
                    WebSocket: failure_detected event → UI red banner
                                         ↓
                         on_pipeline_failure() callback
                                         ↓
                    LangGraph Agent: collect → RAG → LLM → persist → broadcast
                                         ↓
                         WebSocket: ai_analysis_complete → UI
                                         ↓
                    User sees structured troubleshooting suggestions
```

---

## Security Considerations

- Docker socket access limited to the backend container (non-root user)
- API key stored as environment variable (never committed)
- CORS restricted to frontend origin
- File upload restricted to known bioinformatics extensions
- SQLite WAL mode for concurrent async access safety

---

## Scalability Path

| Component | Current | Scale-up Path |
|-----------|---------|---------------|
| Database  | SQLite  | PostgreSQL with connection pool |
| Workflow execution | Local subprocess | Nextflow Tower / AWS Batch |
| AI agent | Single instance | Worker queue (Celery/ARQ) |
| Vector store | Local ChromaDB | Managed Qdrant or Pinecone |
| Log storage | SQLite + files | Elasticsearch / Loki |
| Frontend | Single Nginx | CDN + edge caching |
