"""
backends/ — Pluggable Embedding Backend Implementations

Available backends:
- chromadb: Default, local-first (uses ChromaDB)
- postgres: Enterprise database with pgvector extension
- lancedb: Lightweight, Rust-based, serverless
- Future: qdrant, weaviate, pinecone
"""

from .lancedb_backend import LanceDBBackend
from .postgres_backend import PostgreSQLBackend

__all__ = ["PostgreSQLBackend", "LanceDBBackend"]
