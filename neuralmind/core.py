"""
core.py — NeuralMind Core System
=================================

Main entry point for the NeuralMind adaptive knowledge system.
Orchestrates the knowledge searcher and context selector.
"""

from pathlib import Path

from .context_selector import ContextResult, ContextSelector
from .embedder import KnowledgeSearcher

class NeuralMind:
    """
    Adaptive Neural Knowledge System.
    """

    def __init__(self, project_path: str, db_path: str = None):
        """
        Initialize NeuralMind for a project.

        Args:
            project_path: Path to project root
            db_path: Optional custom path for ChromaDB storage
        """
        self.project_path = Path(project_path)
        self.db_path = db_path

        # Initialize components
        self.searcher = KnowledgeSearcher(project_path, db_path)
        # The selector now needs to be initialized differently, or its role re-evaluated.
        # For now, we'll simplify and focus on the searcher.
        self.selector = None # To be refactored

    def query(self, question: str) -> str:
        """
        Get optimized context for answering a question.
        """
        # This is a simplified query method. The complex context layering
        # of the original design is removed, as it depended on a graph structure
        # that does not exist.
        search_results = self.searcher.search(question, n=15)
        
        # Combine the search result documents into a single context string
        context = "\n\n---\n\n".join([result['document'] for result in search_results])
        
        # Create a simplified response. The original ContextResult is too complex.
        header = f"## Project: {self.project_path.name}\n\n"
        stats = self.get_stats()
        knowledge_info = f"Knowledge Base: {stats.get('total_drawers', 0)} text chunks (drawers) available.\n\n"

        return header + knowledge_info + "## Relevant Information\n\n" + context

    def get_stats(self) -> dict:
        """
        Get current system statistics.
        """
        return self.searcher.get_stats()
