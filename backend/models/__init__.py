"""
Feature extraction module for text vectorization.
"""

from .tfidf_features import TFIDFExtractor, extract_tfidf_features
from .embedding_features import EmbeddingExtractor, extract_embeddings

__all__ = [
    "TFIDFExtractor", "extract_tfidf_features",
    "EmbeddingExtractor", "extract_embeddings"
]