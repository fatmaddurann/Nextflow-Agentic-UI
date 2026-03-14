# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-03-15

### Added

- Nextflow DSL2 RNA-Seq pipeline with six modular processes: FastQC, Trimmomatic, STAR,
  SAMtools, featureCounts, MultiQC
- FastAPI backend with async SQLAlchemy ORM (PostgreSQL + SQLite support), WebSocket log
  streaming, and REST API for workflow lifecycle management
- LangGraph AI agent with five-node graph: log collection → RAG retrieval → failure analysis
  → result persistence → WebSocket broadcast
- ChromaDB knowledge base with 15 curated bioinformatics troubleshooting articles across
  eight categories (STAR errors, Docker issues, memory limits, etc.)
- Docker SDK container manager with async wrappers for list, inspect, restart, stop, remove,
  log streaming, and resource stats
- Real-time log monitor with 15 compiled failure-pattern regexes and position-tracking tail loop
- React dashboard with live log viewer, AI assistant panel, container manager, and knowledge
  base browser
- `simulate_failure` Nextflow profile for end-to-end AI troubleshooting demos
- Docker Compose stack: PostgreSQL 16, ChromaDB, FastAPI backend, Nginx frontend, monitoring
  sidecar
- GitHub Actions CI: ruff lint, pytest, ESLint, Vite build check, Nextflow stub run
- GitHub Actions Docker workflow: backend and frontend image build validation
- Issue templates for bug reports and feature requests
- Contributing guidelines and MIT license

[Unreleased]: https://github.com/fatmaddurann/Nextflow-Agentic-UI/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/fatmaddurann/Nextflow-Agentic-UI/releases/tag/v1.0.0
