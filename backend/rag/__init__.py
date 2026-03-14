"""RAG package — exports KnowledgeBase singleton."""

from .knowledge_base import KNOWLEDGE_BASE, KnowledgeBase, knowledge_base

__all__ = ["knowledge_base", "KnowledgeBase", "KNOWLEDGE_BASE"]
