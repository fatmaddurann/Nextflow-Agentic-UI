"""
services/ai_agent.py
LangGraph-based AI agent for bioinformatics pipeline log analysis and troubleshooting.
Activates automatically when pipeline failures are detected.
"""

import os
import time
from datetime import datetime
from typing import Any, TypedDict

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from database.crud import get_workflow, get_workflow_logs, save_ai_analysis
from database.database import AsyncSessionLocal
from database.models import SeverityLevel
from rag.knowledge_base import knowledge_base
from services.log_monitor import ws_manager

log = structlog.get_logger(__name__)

# LLM Configuration
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
MAX_LOG_LINES = int(os.getenv("MAX_LOG_LINES", "300"))


# Agent State
class AgentState(TypedDict):
    """State passed between LangGraph nodes."""

    workflow_id: str
    workflow_name: str
    pipeline_type: str
    failed_process: str | None
    error_category: str | None
    raw_log_lines: list[str]
    error_logs: list[str]
    rag_documents: list[dict[str, Any]]
    rag_query: str
    analysis: dict[str, Any]
    messages: list[Any]
    retry_count: int


# System Prompt
SYSTEM_PROMPT = """You are an expert bioinformatics platform engineer and pipeline debugging specialist.
You have deep knowledge of:
- Nextflow DSL2 pipeline development and troubleshooting
- Bioinformatics tools: STAR, BWA, Samtools, FastQC, Trimmomatic, featureCounts, MultiQC
- Docker container management and resource allocation
- RNA-Seq and WES analysis workflows
- Common pipeline failure modes and their solutions

Your role is to analyze pipeline failure logs and provide:
1. A clear, concise summary of what went wrong
2. The identified root cause(s)
3. Specific, actionable troubleshooting steps in priority order
4. Preventive measures for the future

Be specific — reference actual log lines, tool names, and parameter names.
Format your response as structured JSON with these exact fields:
{
  "error_summary": "1-2 sentence description of the failure",
  "root_cause": "Technical explanation of the root cause",
  "affected_steps": ["list", "of", "failed", "process", "names"],
  "suggestions": [
    "Step 1: specific action to take",
    "Step 2: specific action to take",
    ...
  ],
  "confidence": 0.0-1.0
}"""


# LangGraph Agent


class BioinformaticsAIAgent:
    """
    LangGraph-based agent that:
    1. Collects pipeline logs and metadata
    2. Retrieves relevant knowledge from the RAG store
    3. Analyses the failure with an LLM
    4. Persists the analysis to the database
    5. Broadcasts results to connected WebSocket clients
    """

    def __init__(self) -> None:
        self._llm: ChatOpenAI | None = None
        self._graph = self._build_graph()

    def _get_llm(self) -> ChatOpenAI:
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=OPENAI_MODEL,
                base_url=OPENAI_BASE_URL,
                temperature=0.1,  # Low temp for consistent technical advice
                max_tokens=2048,
                request_timeout=60,
            )
        return self._llm

    # Graph Construction

    def _build_graph(self) -> Any:
        graph = StateGraph(AgentState)

        graph.add_node("collect_logs", self._node_collect_logs)
        graph.add_node("retrieve_rag", self._node_retrieve_rag)
        graph.add_node("analyze_failure", self._node_analyze_failure)
        graph.add_node("persist_results", self._node_persist_results)
        graph.add_node("broadcast_results", self._node_broadcast_results)

        graph.set_entry_point("collect_logs")
        graph.add_edge("collect_logs", "retrieve_rag")
        graph.add_edge("retrieve_rag", "analyze_failure")
        graph.add_edge("analyze_failure", "persist_results")
        graph.add_edge("persist_results", "broadcast_results")
        graph.add_edge("broadcast_results", END)

        return graph.compile()

    # Graph Nodes

    async def _node_collect_logs(self, state: AgentState) -> AgentState:
        """Fetch workflow metadata and error logs from the database."""
        workflow_id = state["workflow_id"]
        log.info("ai_agent_collecting_logs", workflow_id=workflow_id)

        try:
            async with AsyncSessionLocal() as db:
                workflow = await get_workflow(db, workflow_id)
                all_logs = await get_workflow_logs(db, workflow_id, limit=MAX_LOG_LINES)

            if workflow:
                state["workflow_name"] = workflow.name
                state["pipeline_type"] = str(workflow.pipeline_type)
                state["failed_process"] = workflow.failed_process

            # Separate error/warning logs for focused analysis
            error_lines = [
                entry.raw_line or entry.message
                for entry in all_logs
                if entry.level
                in (SeverityLevel.ERROR, SeverityLevel.CRITICAL, SeverityLevel.WARNING)
            ]

            state["raw_log_lines"] = [entry.raw_line or entry.message for entry in all_logs[-100:]]
            state["error_logs"] = error_lines[-50:]  # Last 50 error lines

            log.info(
                "ai_agent_logs_collected",
                workflow_id=workflow_id,
                total_logs=len(all_logs),
                error_lines=len(error_lines),
            )
        except Exception as exc:
            log.error("ai_agent_collect_error", workflow_id=workflow_id, error=str(exc))
            state["error_logs"] = [f"Log collection error: {exc}"]

        return state

    async def _node_retrieve_rag(self, state: AgentState) -> AgentState:
        """Build a RAG query and retrieve relevant knowledge base documents."""
        log.info("ai_agent_retrieving_rag", workflow_id=state["workflow_id"])

        # Build a focused query from error context
        error_summary = "\n".join(state["error_logs"][:10])
        category = state.get("error_category")
        query_parts = [
            f"Pipeline: {state.get('pipeline_type', 'rnaseq')}",
            f"Failed process: {state.get('failed_process') or 'unknown'}",
            f"Error logs: {error_summary[:500]}",
        ]
        query = " ".join(query_parts)
        state["rag_query"] = query

        # Retrieve from knowledge base
        docs = await knowledge_base.retrieve(
            query=query,
            top_k=5,
            category_filter=category,
        )
        state["rag_documents"] = docs

        log.info(
            "ai_agent_rag_retrieved",
            workflow_id=state["workflow_id"],
            doc_count=len(docs),
            top_relevance=docs[0]["relevance"] if docs else 0.0,
        )
        return state

    async def _node_analyze_failure(self, state: AgentState) -> AgentState:
        """Call the LLM to analyse the failure using logs + RAG context."""
        log.info("ai_agent_analyzing", workflow_id=state["workflow_id"])

        llm = self._get_llm()

        # Build the human message with full context
        rag_context = self._format_rag_context(state["rag_documents"])
        error_block = "\n".join(state["error_logs"][:30]) or "No error lines captured"

        human_message = f"""
Analyse this failed bioinformatics pipeline run:

=== WORKFLOW METADATA ===
- Workflow ID: {state["workflow_id"]}
- Pipeline: {state.get("pipeline_type", "RNA-Seq")}
- Failed process: {state.get("failed_process") or "Unknown"}
- Error category: {state.get("error_category") or "Unknown"}

=== ERROR LOGS (most recent {len(state["error_logs"])} error lines) ===
{error_block}

=== RECENT LOG TAIL ===
{chr(10).join(state["raw_log_lines"][-20:])}

=== RELEVANT KNOWLEDGE BASE ARTICLES ===
{rag_context}

Based on the logs and knowledge base, provide your analysis as JSON exactly matching this schema:
{{
  "error_summary": "...",
  "root_cause": "...",
  "affected_steps": ["..."],
  "suggestions": ["Step 1: ...", "Step 2: ...", "..."],
  "confidence": 0.85
}}
"""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=human_message),
        ]

        start_time = time.time()
        analysis = {
            "error_summary": "Analysis failed",
            "root_cause": "",
            "affected_steps": [],
            "suggestions": ["Check logs manually"],
            "confidence": 0.0,
        }

        try:
            response = await llm.ainvoke(messages)
            raw_text = response.content
            latency = time.time() - start_time

            # Parse the JSON response
            import json
            import re

            # Extract JSON block from the response
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                analysis.update(parsed)

            analysis["_raw_response"] = raw_text
            analysis["_model"] = OPENAI_MODEL
            analysis["_tokens"] = (
                response.usage_metadata.get("total_tokens", 0)
                if hasattr(response, "usage_metadata")
                else 0
            )
            analysis["_latency_s"] = round(latency, 2)

            log.info(
                "ai_agent_analysis_complete",
                workflow_id=state["workflow_id"],
                confidence=analysis.get("confidence", 0.0),
                latency=latency,
            )

        except Exception as exc:
            log.error("ai_agent_analyze_error", workflow_id=state["workflow_id"], error=str(exc))
            analysis["error_summary"] = f"AI analysis encountered an error: {exc}"
            analysis["suggestions"] = [
                "Review the error logs manually.",
                "Check the Nextflow trace report for exit codes.",
                "Consult the tool documentation for the failed process.",
            ]

        state["analysis"] = analysis
        return state

    async def _node_persist_results(self, state: AgentState) -> AgentState:
        """Save the AI analysis to the database."""
        a = state["analysis"]
        try:
            async with AsyncSessionLocal() as db:
                await save_ai_analysis(
                    db,
                    {
                        "workflow_id": state["workflow_id"],
                        "error_summary": a.get("error_summary", ""),
                        "root_cause": a.get("root_cause"),
                        "affected_steps": a.get("affected_steps", []),
                        "suggestions": a.get("suggestions", []),
                        "rag_sources": [
                            {
                                "doc_id": d["doc_id"],
                                "title": d["title"],
                                "relevance": d["relevance"],
                            }
                            for d in state["rag_documents"]
                        ],
                        "confidence": float(a.get("confidence", 0.0)),
                        "model_used": a.get("_model", OPENAI_MODEL),
                        "tokens_used": int(a.get("_tokens", 0)),
                        "full_response": a.get("_raw_response"),
                    },
                )
                await db.commit()
            log.info("ai_agent_analysis_persisted", workflow_id=state["workflow_id"])
        except Exception as exc:
            log.error("ai_agent_persist_error", workflow_id=state["workflow_id"], error=str(exc))
        return state

    async def _node_broadcast_results(self, state: AgentState) -> AgentState:
        """Push the analysis to connected WebSocket clients."""
        a = state["analysis"]
        await ws_manager.broadcast(
            state["workflow_id"],
            {
                "type": "ai_analysis_complete",
                "workflow_id": state["workflow_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "error_summary": a.get("error_summary"),
                "root_cause": a.get("root_cause"),
                "affected_steps": a.get("affected_steps", []),
                "suggestions": a.get("suggestions", []),
                "confidence": a.get("confidence", 0.0),
                "rag_sources": [
                    {"doc_id": d["doc_id"], "title": d["title"], "relevance": d["relevance"]}
                    for d in state["rag_documents"]
                ],
            },
        )
        return state

    # Public Entry Point

    async def analyze_workflow(
        self,
        workflow_id: str,
        error_category: str | None = None,
        trigger_line: str | None = None,
    ) -> dict[str, Any]:
        """
        Run the full analysis graph for a failed workflow.
        Returns the final analysis dict.
        """
        log.info(
            "ai_agent_triggered",
            workflow_id=workflow_id,
            category=error_category,
        )

        initial_state: AgentState = {
            "workflow_id": workflow_id,
            "workflow_name": "",
            "pipeline_type": "rnaseq",
            "failed_process": None,
            "error_category": error_category,
            "raw_log_lines": [trigger_line] if trigger_line else [],
            "error_logs": [trigger_line] if trigger_line else [],
            "rag_documents": [],
            "rag_query": "",
            "analysis": {},
            "messages": [],
            "retry_count": 0,
        }

        final_state = await self._graph.ainvoke(initial_state)
        return final_state.get("analysis", {})

    # Helpers

    @staticmethod
    def _format_rag_context(docs: list[dict[str, Any]]) -> str:
        """Format retrieved documents into a prompt-friendly string."""
        if not docs:
            return "No relevant knowledge base articles found."

        parts = []
        for i, d in enumerate(docs[:3], 1):  # Top 3 most relevant
            parts.append(
                f"[Article {i}] {d['title']} (relevance: {d['relevance']:.2f})\n"
                f"{d['content'][:600].strip()}"
            )
        return "\n\n---\n\n".join(parts)


# Singleton instance
ai_agent = BioinformaticsAIAgent()


# Failure callback (registered with LogMonitor)
async def on_pipeline_failure(
    workflow_id: str,
    error_category: str,
    trigger_line: str,
) -> None:
    """
    Called by the LogMonitor when a failure pattern is detected.
    Launches the AI analysis graph asynchronously.
    """
    log.info(
        "auto_ai_analysis_triggered",
        workflow_id=workflow_id,
        category=error_category,
    )
    await ai_agent.analyze_workflow(
        workflow_id=workflow_id,
        error_category=error_category,
        trigger_line=trigger_line,
    )
