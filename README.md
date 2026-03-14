<div align="center">

# Nextflow-Agentic-UI

**AI-powered pipeline management for bioinformatics workflows**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Nextflow](https://img.shields.io/badge/Nextflow-DSL2-1abc9c)](https://nextflow.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Run, monitor, and debug Nextflow pipelines through an intelligent interface that automatically analyses failures and suggests fixes using RAG-powered AI.

**Author:** [Fatma Duran](https://github.com/fatmaddurann)

</div>

---

## Overview

Nextflow-Agentic-UI combines a Nextflow RNA-Seq pipeline, a FastAPI backend, and a React dashboard into a single platform. When a pipeline fails, an AI agent built with LangGraph automatically analyses the logs, retrieves relevant solutions from a curated knowledge base, and presents actionable troubleshooting steps — all in real time via WebSocket.

```
React UI  ←── REST / WebSocket ──►  FastAPI  ──► Nextflow subprocess
                                       │
                              SQLite / PostgreSQL
                                       │
                              LangGraph AI Agent
                              GPT-4o + ChromaDB RAG
```

## Features

- **RNA-Seq pipeline** (DSL2) — FastQC → Trimmomatic → STAR → SAMtools → featureCounts → MultiQC
- **Pipeline API** — start, stop, resume workflows; Docker container lifecycle management
- **Real-time log streaming** — WebSocket-based log tailing with pattern-based failure detection
- **AI troubleshooting** — automatic root-cause analysis with prioritised fix suggestions
- **RAG knowledge base** — 15 curated articles across 8 error categories (STAR, Docker, memory, GTF mismatches, etc.)
- **React dashboard** — live log viewer, AI assistant panel, container manager, knowledge base browser

## Quick Start

**Prerequisites:** Docker + Docker Compose, OpenAI API key

```bash
git clone https://github.com/fatmaddurann/Nextflow-Agentic-UI.git
cd Nextflow-Agentic-UI
cp .env.example .env          # add your OPENAI_API_KEY
docker compose up -d
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| ChromaDB | http://localhost:8001 |

## Running a Pipeline

**Via the UI:** Run Pipeline → fill in parameters → Launch → monitor live logs

**Via the API:**
```bash
curl -X POST http://localhost:8000/api/v1/workflows/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HepG2 RNA-Seq",
    "pipeline_type": "rnaseq",
    "profile": "docker",
    "reads": "/data/fastq/*_{1,2}.fastq.gz",
    "star_index": "/ref/star_index",
    "gtf": "/ref/genes.gtf"
  }'
```

**Simulate a failure** (triggers the AI agent demo):
```bash
curl -X POST http://localhost:8000/api/v1/workflows/ \
  -H "Content-Type: application/json" \
  -d '{"name": "failure-demo", "profile": "simulate_failure"}'
```

## AI Agent

When a failure is detected, the LangGraph agent runs a 5-step graph:

1. **Collect logs** — fetch workflow logs and metadata from the database
2. **Retrieve RAG** — embed the error query and retrieve matching knowledge base articles from ChromaDB
3. **Analyse** — send logs + retrieved context to GPT-4o with a structured JSON output schema
4. **Persist** — save the analysis to the database
5. **Broadcast** — push results to all connected WebSocket clients

See [`docs/AI_TROUBLESHOOTING_DEMO.md`](docs/AI_TROUBLESHOOTING_DEMO.md) for a full walkthrough of a simulated STAR index failure and the agent's response.

## Project Structure

```
Nextflow-Agentic-UI/
├── pipeline/               # Nextflow DSL2 RNA-Seq pipeline
│   ├── main.nf
│   ├── nextflow.config
│   └── modules/            # fastqc, trimmomatic, star, samtools, featurecounts, multiqc
├── backend/                # FastAPI application
│   ├── main.py
│   ├── api/routes/         # workflows, logs, containers
│   ├── database/           # SQLAlchemy models + async CRUD
│   ├── services/           # workflow manager, container manager, log monitor, AI agent
│   └── rag/                # ChromaDB knowledge base
├── frontend/               # React + Vite + Tailwind
│   └── src/components/     # Dashboard, WorkflowRunner, LogViewer, AIAssistant, ...
├── monitoring/             # Log monitor sidecar
├── docs/                   # Architecture + AI demo walkthrough
└── docker-compose.yml
```

## Tech Stack

| Layer | Technology |
|---|---|
| Pipeline | Nextflow DSL2, biocontainers |
| Backend | Python 3.11, FastAPI, SQLAlchemy (async) |
| AI | LangChain, LangGraph, OpenAI GPT-4o |
| RAG | ChromaDB, OpenAI `text-embedding-3-small` |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Frontend | React 18, Vite, Tailwind CSS, Recharts |
| Infra | Docker Compose, Nginx |

## Development

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Pipeline (stub run, no real data needed)
cd pipeline && nextflow run main.nf -profile test -stub-run
```

## Contributing

See [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md).

## License

[MIT](LICENSE)
