"""
Vector store module for FAISS-based retrieval.
"""

from .faiss_integration import FaissIndex, FaissVectorStore, build_vector_store_from_embeddings

__all__ = ["FaissIndex", "FaissVectorStore", "build_vector_store_from_embeddings"]