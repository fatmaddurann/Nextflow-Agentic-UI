"""
rag/knowledge_base.py
Builds and queries the RAG knowledge base for bioinformatics pipeline errors.
Uses ChromaDB as the vector store and OpenAI Embeddings.
"""

import os
import uuid
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./knowledge_base/chroma_db")
CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
RAG_COLLECTION = "bioinformatics_errors"
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))


# Knowledge Base Documents
KNOWLEDGE_BASE: list[dict[str, Any]] = [
    # STAR Errors
    {
        "id": "star-001",
        "title": "STAR: Genome Index Not Found (genomeDir)",
        "category": "star_errors",
        "tags": ["STAR", "alignment", "index", "genomeDir"],
        "content": """
Problem: STAR fails with "EXITING because of FATAL ERROR: could not open genome files".

Cause: The STAR genome index directory is missing, empty, or its path is incorrect.
This typically happens when:
- The --star_index parameter points to a non-existent directory
- The STAR_GENOMEGENERATE step was skipped or failed previously
- The index was generated with a different STAR version

Solution:
1. Verify the star_index path: ls -la /path/to/star_index/
2. Check for required files: Genome, SA, SAindex, chrName.txt
3. Rebuild the index:
   nextflow run main.nf --genome genome.fa --gtf genes.gtf (omit --star_index)
4. If using Docker, ensure the volume mount includes the index directory
5. Match STAR version: genome index must match the STAR binary version

Prevention: Store the STAR index on persistent storage; cache it between runs.
        """,
        "source": "STAR Manual v2.7 + common bioinformatics troubleshooting",
    },
    {
        "id": "star-002",
        "title": "STAR: genomeSAindexNbases Too Large",
        "category": "star_errors",
        "tags": ["STAR", "alignment", "genomeSAindexNbases", "small genome"],
        "content": """
Problem: STAR fails with "FATAL ERROR: genomeSAindexNbases X is too large".

Cause: The genomeSAindexNbases parameter is set too large for the reference genome.
For small genomes (< 1 Gb), STAR requires a smaller value.

Formula: genomeSAindexNbases = min(14, floor(log2(GenomeLength) / 2 - 1))
- Human genome (~3 Gb):  use 14 (default)
- Mouse genome (~2.5 Gb): use 14
- Small test genome:      use 11 or lower

Solution:
1. Calculate: python3 -c "import math; print(min(14, int(math.log2(3e9)/2 - 1)))"
2. Pass to pipeline: --extra_params '{"genomeSAindexNbases": "11"}'
3. Or set in nextflow.config: params.star_genome_sa_index_nbases = 11

Note: This error often appears in test runs with small synthetic genomes.
        """,
        "source": "STAR Manual — Genome generation parameters",
    },
    {
        "id": "star-003",
        "title": "STAR: Insufficient Memory for Alignment",
        "category": "star_errors",
        "tags": ["STAR", "memory", "RAM", "OOM", "limitBAMsortRAM"],
        "content": """
Problem: STAR fails with "EXITING: due to fatal ERROR: limitBAMsortRAM" or is killed by OOM killer.

Cause: STAR requires substantial RAM — typically 30-40 GB for the human genome.
Default Nextflow memory allocations may be insufficient.

Solution:
1. Increase memory in nextflow.config:
   withName: STAR_ALIGN { memory = { check_max(40.GB * task.attempt, 'memory') } }
2. Increase limitBAMsortRAM in the STAR command (already handled in the module)
3. If using Docker: ensure the container has sufficient memory limits
4. Use --outSAMtype BAM Unsorted + sort separately to reduce peak RAM
5. If running locally, check available RAM: free -h

Prevention: Pre-calculate required memory based on genome size before running.
        """,
        "source": "STAR GitHub Issues + Biostars community",
    },
    # FastQC Errors
    {
        "id": "fastqc-001",
        "title": "FastQC: Invalid or Corrupt FASTQ Input",
        "category": "fastqc_errors",
        "tags": ["FastQC", "FASTQ", "input", "corrupt", "format"],
        "content": """
Problem: FastQC fails with "uk.ac.babraham.FastQC.Sequence.SequenceFormatException" or similar Java exceptions.

Cause: The input FASTQ file is corrupt, truncated, or uses a non-standard format.
Common scenarios:
- Incomplete download (check file size)
- Gzip-compressed file is corrupt
- Wrong file format (e.g., FASTA instead of FASTQ)
- File from Windows has Windows line endings (CRLF)

Solution:
1. Verify file integrity: gzip -t sample_R1.fastq.gz
2. Check first few lines: zcat sample_R1.fastq.gz | head -8
3. Verify FASTQ format: line 1 must start with @, line 3 must be +
4. Re-download or re-demultiplex the sample
5. Convert Windows line endings: sed -i 's/\r//' sample.fastq

Prevention: Always validate input files before launching the pipeline.
        """,
        "source": "FastQC documentation + Biostars troubleshooting",
    },
    {
        "id": "fastqc-002",
        "title": "FastQC: Read Pair Mismatch",
        "category": "fastqc_errors",
        "tags": ["FastQC", "paired-end", "read pair", "mismatch"],
        "content": """
Problem: Paired-end FASTQ files have different read counts.

Cause: R1 and R2 files have a different number of reads, indicating a corrupt or
truncated pair. This can be caused by:
- Failed secondary demultiplexing
- Partial transfer of files
- File corruption during storage

Solution:
1. Count reads in each file:
   echo "R1: $(zcat sample_R1.fastq.gz | wc -l | awk '{print $1/4}')"
   echo "R2: $(zcat sample_R2.fastq.gz | wc -l | awk '{print $1/4}')"
2. If counts differ, re-download or re-demultiplex
3. Use repair.sh from BBTools to fix paired-end files:
   repair.sh in1=R1.fastq.gz in2=R2.fastq.gz out1=fixed_R1.fastq.gz out2=fixed_R2.fastq.gz

Prevention: Implement a pre-pipeline QC step that validates read pair counts.
        """,
        "source": "Bioinformatics best practices",
    },
    # Docker / Container Errors
    {
        "id": "docker-001",
        "title": "Docker: Container Image Pull Failed",
        "category": "docker_errors",
        "tags": ["Docker", "container", "pull", "registry", "network"],
        "content": """
Problem: Nextflow fails with "Unable to find image" or "manifest unknown: manifest unknown".

Cause: Docker cannot pull the container image specified in nextflow.config.
Possible reasons:
- No internet connectivity in the execution environment
- Wrong image name or tag (typo)
- Container registry is down
- Private registry requires authentication

Solution:
1. Test connectivity: docker pull biocontainers/fastqc:v0.11.9_cv8
2. Verify image name on Docker Hub: https://hub.docker.com
3. Pre-pull images before running: docker pull <image>
4. For private registries: docker login registry.example.com
5. Use --offline mode after pulling: nextflow run ... (images cached locally)
6. Check quay.io status: https://status.quay.io

Prevention: Pre-pull all container images and use a local registry mirror.
        """,
        "source": "Nextflow documentation — Docker integration",
    },
    {
        "id": "docker-002",
        "title": "Docker: Permission Denied — Cannot Connect to Daemon",
        "category": "docker_errors",
        "tags": ["Docker", "permission", "daemon", "socket", "unix"],
        "content": """
Problem: "Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock"

Cause: The user running Nextflow does not have permission to access the Docker socket.

Solution:
1. Add user to docker group: sudo usermod -aG docker $USER && newgrp docker
2. Restart Docker service: sudo systemctl restart docker
3. In containers: mount the socket with correct permissions:
   docker run -v /var/run/docker.sock:/var/run/docker.sock ...
4. Set appropriate group: sudo chown root:docker /var/run/docker.sock
5. For rootless Docker: export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock

Prevention: Configure CI/CD and execution environments with correct group membership.
        """,
        "source": "Docker documentation — Post-installation steps for Linux",
    },
    {
        "id": "docker-003",
        "title": "Docker: Container Killed (OOMKilled)",
        "category": "docker_errors",
        "tags": ["Docker", "OOM", "memory", "kill", "cgroup"],
        "content": """
Problem: Container exits with status 137 and Docker shows OOMKilled=true.

Cause: The container exceeded its memory limit and was killed by the OS.
Exit code 137 = 128 + 9 (SIGKILL).

Solution:
1. Check container stats: docker inspect <container_id> | grep -i oom
2. Increase memory limit in nextflow.config:
   withName: STAR_ALIGN { memory = '64.GB' }
3. If using Docker with --memory flag, remove it or increase:
   docker run --memory=64g ...
4. Profile the tool's peak memory before setting limits
5. Reduce input data size for testing

Diagnosis: Exit code 137 in trace.txt confirms OOMKill.
Prevention: Always set memory limits 20% above profiled peak usage.
        """,
        "source": "Docker + Linux OOM killer documentation",
    },
    # Trimmomatic Errors
    {
        "id": "trimmomatic-001",
        "title": "Trimmomatic: Adapter File Not Found",
        "category": "trimmomatic_errors",
        "tags": ["Trimmomatic", "adapter", "ILLUMINACLIP", "TruSeq"],
        "content": """
Problem: Trimmomatic fails with "ILLUMINACLIP: Could not load adapters file".

Cause: The adapter FASTA file specified in --trimmomatic_adapter does not exist
at the given path inside the container.

Solution:
1. Verify adapter file exists: ls -la $NF_ADAPTER_PATH
2. Standard adapters ship with Trimmomatic:
   /usr/share/trimmomatic/adapters/TruSeq3-PE.fa (inside container)
3. Mount the adapter file as a volume or copy it to the container's expected path
4. Use the bundled adapter by specifying the correct container-internal path:
   params.trimmomatic_adapter = "/usr/share/trimmomatic/adapters/TruSeq3-PE.fa"
5. Alternatively, disable adapter trimming: omit the ILLUMINACLIP step

Common adapter files: TruSeq2-PE.fa, TruSeq3-PE.fa, NexteraPE-PE.fa, TruSeq3-SE.fa
        """,
        "source": "Trimmomatic documentation",
    },
    # Nextflow / DSL2 Errors
    {
        "id": "nextflow-001",
        "title": "Nextflow: Missing Required Parameter",
        "category": "nextflow_errors",
        "tags": ["Nextflow", "parameters", "params", "missing", "required"],
        "content": """
Problem: Pipeline fails with "Missing required parameter" or "No argument provided for --param".

Cause: A required Nextflow parameter was not supplied on the command line or in nextflow.config.

Solution:
1. Review required params in the pipeline script (params block in main.nf)
2. Supply missing params at runtime:
   nextflow run main.nf --reads '/data/*.fastq.gz' --genome /ref/genome.fa --gtf /ref/genes.gtf
3. Or add defaults in nextflow.config:
   params { reads = '/data/*.fastq.gz' }
4. Check the params validation section in main.nf for exact required fields
5. For the RNA-Seq pipeline, minimum required: --reads + (--star_index OR --genome+--gtf)

Common missing params: --reads, --genome, --gtf, --star_index
        """,
        "source": "Nextflow documentation — Parameters",
    },
    {
        "id": "nextflow-002",
        "title": "Nextflow: Channel Value Type Mismatch",
        "category": "nextflow_errors",
        "tags": ["Nextflow", "DSL2", "channel", "tuple", "type", "mismatch"],
        "content": """
Problem: "No signature of method" or "Cannot call method X on type Y" errors.

Cause: A Nextflow DSL2 channel emits a different type than the receiving process expects.
Common mismatches:
- Passing a single path where a tuple (meta, path) is expected
- Passing a list where a single value is expected
- Missing metadata map in the channel

Solution:
1. Check the process input declaration: tuple val(meta), path(reads)
2. Trace the channel with .view(): channel.view { "item: $it" }
3. Transform the channel to match:
   ch_reads.map { sample_id, reads -> [[id: sample_id], reads] }
4. Use .collect() for processes expecting all items together
5. Verify module input/output signatures match the main workflow channels

Debug tip: Add .view() after every channel transformation to inspect values.
        """,
        "source": "Nextflow DSL2 documentation + community troubleshooting",
    },
    {
        "id": "nextflow-003",
        "title": "Nextflow: Work Directory Permissions / NFS Issues",
        "category": "nextflow_errors",
        "tags": ["Nextflow", "work directory", "NFS", "permissions", "scratch"],
        "content": """
Problem: Nextflow fails with permission errors or stale file handle on NFS work directories.

Cause: Work directory is on NFS with locking issues, or incorrect permissions.

Solution:
1. Change work directory to local fast storage:
   nextflow run main.nf -work-dir /tmp/nf_work
2. Or set in nextflow.config: workDir = '/scratch/nf_work'
3. Fix permissions: chmod -R 755 /path/to/work_dir
4. For NFS: add 'nolock' mount option and set NXF_WORK to local path
5. Use stageInMode = 'copy' if symlinks across filesystems cause issues

NFS Tip: Nextflow relies heavily on symlinks; NFS with nolock can cause issues.
Use --work-dir on a POSIX-compliant local filesystem for best performance.
        """,
        "source": "Nextflow documentation — Execution work directory",
    },
    # featureCounts / Quantification Errors
    {
        "id": "featurecounts-001",
        "title": "featureCounts: Annotation / GTF Mismatch",
        "category": "featurecounts_errors",
        "tags": ["featureCounts", "GTF", "annotation", "chromosome names", "genome assembly"],
        "content": """
Problem: featureCounts assigns 0 reads or fails with annotation errors.

Cause: Chromosome naming mismatch between BAM file and GTF:
- BAM uses 'chr1' but GTF uses '1' (or vice versa)
- GTF from a different genome assembly than the reference used for alignment
- GTF file is malformed or uses a non-standard format

Solution:
1. Check chromosome names in BAM: samtools view -H sample.bam | grep @SQ | head
2. Check chromosome names in GTF: head -100 genes.gtf | grep -v '#' | cut -f1 | sort -u
3. If mismatch, fix the GTF: sed 's/^chr//' genes.gtf > genes_nochr.gtf (remove chr prefix)
4. Always use matching genome + GTF from the same source (Ensembl or UCSC, same version)
5. Pass --allowMultiOverlap if needed for gene-dense regions

Assembly matching: GENCODE GRCh38 GTF → GRCh38 FASTA; Ensembl GRCh38.110 GTF → GRCh38 FASTA
        """,
        "source": "featureCounts manual + GENCODE/Ensembl documentation",
    },
    # Memory / Resource Errors
    {
        "id": "memory-001",
        "title": "General: Out of Memory — Process Killed",
        "category": "memory_errors",
        "tags": ["memory", "OOM", "RAM", "killed", "exit 137", "resource"],
        "content": """
Problem: A bioinformatics process is killed mid-execution with exit code 137 or 1.

Cause: Insufficient RAM allocated to the process. Common memory-hungry tools:
- STAR alignment: 30-40 GB for human genome
- BWA MEM: 5-10 GB for human genome
- featureCounts: 2-8 GB depending on BAM size
- Samtools sort: memory scales with BAM size and -m flag

Solution:
1. Identify peak memory from a previous run in trace.txt (peak_rss column)
2. Increase memory in nextflow.config:
   withName: 'STAR_ALIGN' { memory = { check_max(48.GB * task.attempt, 'memory') } }
3. Use automatic retry with escalating memory:
   errorStrategy = { task.exitStatus == 137 ? 'retry' : 'finish' }
   maxRetries = 3
   memory = { check_max(8.GB * task.attempt, 'memory') }
4. Monitor memory during run: watch -n1 free -h
5. Use memusg or /usr/bin/time -v to profile tool memory requirements

Heuristic: Set memory limit = 1.5 × peak observed RSS from a test run.
        """,
        "source": "Nextflow best practices + Bioinformatics resource management",
    },
    # Disk Space Errors
    {
        "id": "disk-001",
        "title": "Disk Space Exhausted During Pipeline Run",
        "category": "disk_errors",
        "tags": ["disk", "storage", "space", "quota", "work directory"],
        "content": """
Problem: Pipeline fails with "No space left on device" or "Disk quota exceeded".

Cause: Nextflow work directories accumulate large intermediate files.
A typical WGS pipeline can generate 100 GB+ of intermediate BAM files.

Solution:
1. Check disk usage: df -h /path/to/work && du -sh /path/to/work/*
2. Clean previous run caches: nextflow clean -f
3. Remove exited Docker containers: docker container prune
4. Mount a larger volume for the work directory
5. Use -work-dir to point to a larger partition
6. Enable automatic cleanup in nextflow.config:
   cleanup = true  (removes successful task work dirs)

Space estimation: Total input size × 10-20× for intermediate files (typical RNA-Seq)
        """,
        "source": "Nextflow documentation + DevOps best practices",
    },
]


# KnowledgeBase Class


class KnowledgeBase:
    """
    Manages the ChromaDB vector store for bioinformatics pipeline error RAG.
    Supports both local persistence and remote ChromaDB server.
    """

    def __init__(self) -> None:
        self._collection = None
        self._embeddings = None

    async def initialize(self) -> None:
        """
        Set up the ChromaDB collection and load/index documents.
        Should be called once at application startup.
        """
        try:
            await self._setup_chroma()
            await self._setup_embeddings()
            await self._index_documents()
            log.info("knowledge_base_initialized", doc_count=len(KNOWLEDGE_BASE))
        except Exception as exc:
            log.error("knowledge_base_init_failed", error=str(exc))

    async def _setup_chroma(self) -> None:
        """Create or connect to ChromaDB collection."""
        import chromadb
        from chromadb.config import Settings

        if CHROMA_HOST:
            # Remote ChromaDB (running as a service)
            client = chromadb.HttpClient(
                host=CHROMA_HOST,
                port=CHROMA_PORT,
                settings=Settings(anonymized_telemetry=False),
            )
        else:
            # Local persistent ChromaDB
            Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(
                path=CHROMA_PERSIST_DIR,
                settings=Settings(anonymized_telemetry=False),
            )

        self._collection = client.get_or_create_collection(
            name=RAG_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    async def _setup_embeddings(self) -> None:
        """Initialize the embedding function."""
        from langchain_openai import OpenAIEmbeddings

        self._embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    async def _index_documents(self) -> None:
        """Index all knowledge base documents if not already present."""
        if self._collection is None:
            return

        existing = set(self._collection.get(include=[])["ids"])
        new_docs = [d for d in KNOWLEDGE_BASE if d["id"] not in existing]

        if not new_docs:
            log.info("knowledge_base_up_to_date", existing_count=len(existing))
            return

        texts = [d["content"].strip() for d in new_docs]
        ids = [d["id"] for d in new_docs]
        metadatas = [
            {
                "title": d["title"],
                "category": d["category"],
                "tags": ", ".join(d.get("tags", [])),
                "source": d.get("source", ""),
            }
            for d in new_docs
        ]

        # Embed in batches of 20 (API rate-limit friendly)
        batch_size = 20
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embs = await self._embeddings.aembed_documents(batch)
            all_embeddings.extend(embs)

        self._collection.add(
            ids=ids,
            documents=texts,
            embeddings=all_embeddings,
            metadatas=metadatas,
        )
        log.info("knowledge_base_indexed", new_docs=len(new_docs))

    async def retrieve(
        self,
        query: str,
        top_k: int = RAG_TOP_K,
        category_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the most relevant knowledge base documents for a query.
        Returns a list of dicts with content, metadata, and relevance score.
        """
        if self._collection is None or self._embeddings is None:
            log.warning("knowledge_base_not_initialized")
            return []

        try:
            query_embedding = await self._embeddings.aembed_query(query)

            where = {"category": category_filter} if category_filter else None

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, self._collection.count()),
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            documents = []
            for i, (doc, meta, dist) in enumerate(
                zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                    strict=False,
                )
            ):
                relevance = max(0.0, 1.0 - dist)  # Convert cosine distance to similarity
                documents.append(
                    {
                        "doc_id": results["ids"][0][i],
                        "title": meta.get("title", ""),
                        "category": meta.get("category", ""),
                        "content": doc,
                        "relevance": round(relevance, 4),
                        "source": meta.get("source", ""),
                    }
                )

            # Sort by relevance
            documents.sort(key=lambda x: x["relevance"], reverse=True)
            return documents

        except Exception as exc:
            log.error("knowledge_base_retrieve_error", error=str(exc))
            return []

    async def add_document(self, doc: dict[str, Any]) -> str:
        """Add a new document to the knowledge base."""
        if self._collection is None:
            raise RuntimeError("Knowledge base not initialized")

        doc_id = doc.get("id") or str(uuid.uuid4())
        content = doc["content"].strip()
        metadata = {
            "title": doc.get("title", ""),
            "category": doc.get("category", ""),
            "tags": ", ".join(doc.get("tags", [])),
            "source": doc.get("source", ""),
        }

        embedding = await self._embeddings.aembed_query(content)
        self._collection.add(
            ids=[doc_id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata],
        )
        log.info("knowledge_base_doc_added", doc_id=doc_id)
        return doc_id

    async def health_check(self) -> str:
        """Return 'ok' if the vector store is reachable."""
        try:
            if self._collection is not None:
                self._collection.count()
                return "ok"
            return "not_initialized"
        except Exception:
            return "unavailable"


# Singleton instance
knowledge_base = KnowledgeBase()
