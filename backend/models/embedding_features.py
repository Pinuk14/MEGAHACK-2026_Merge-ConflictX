"""
Transformer Embedding Feature Extraction Module
================================================

Implements dense embedding extraction using sentence-transformers.
Pluggable extractor for semantic similarity and retrieval.

Features:
- Multiple model support
- Batch processing
- GPU acceleration when available
- Embedding normalization
"""

from pathlib import Path
import json
import pickle
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Attempt to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "sentence-transformers not available. "
        "Install with: pip install sentence-transformers"
    )


@dataclass
class EmbeddingConfig:
    """Configuration for embedding extraction."""
    model_name: str = "all-MiniLM-L6-v2"  # Default model
    batch_size: int = 32  # Batch size for encoding
    normalize: bool = True  # L2 normalize embeddings
    show_progress: bool = True  # Show progress bar
    device: Optional[str] = None  # Device (cuda, cpu, or auto)
    max_seq_length: Optional[int] = None  # Max sequence length


# Recommended models for different use cases
RECOMMENDED_MODELS = {
    "fast": "all-MiniLM-L6-v2",  # 384 dims, fast
    "balanced": "all-mpnet-base-v2",  # 768 dims, good quality
    "multilingual": "paraphrase-multilingual-MiniLM-L12-v2",  # 384 dims
    "large": "all-roberta-large-v1",  # 1024 dims, high quality
    "semantic_search": "multi-qa-MiniLM-L6-cos-v1",  # Optimized for search
}


class EmbeddingExtractor:
    """
    Extracts dense embeddings using sentence-transformers.
    
    Uses pre-trained transformer models to generate semantic
    embeddings for text documents.
    
    Attributes:
        config: EmbeddingConfig instance
        model: SentenceTransformer model
        embedding_dim: Dimensionality of embeddings
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """
        Initialize the embedding extractor.
        
        Args:
            config: Optional embedding configuration
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required for embedding extraction. "
                "Install with: pip install sentence-transformers"
            )
        
        self.config = config or EmbeddingConfig()
        self.model = None
        self.embedding_dim = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load the sentence transformer model."""
        logger.info(f"Loading embedding model: {self.config.model_name}")
        
        try:
            self.model = SentenceTransformer(
                self.config.model_name,
                device=self.config.device
            )
            
            if self.config.max_seq_length:
                self.model.max_seq_length = self.config.max_seq_length
            
            # Get embedding dimension
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            
            logger.info(
                f"✅ Model loaded: {self.config.model_name} "
                f"(dim={self.embedding_dim})"
            )
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def encode(
        self,
        texts: List[str],
        show_progress: Optional[bool] = None
    ) -> np.ndarray:
        """
        Encode texts to embeddings.
        
        Args:
            texts: List of text documents
            show_progress: Override progress bar setting
            
        Returns:
            Numpy array of embeddings (N x dim)
        """
        if not texts:
            return np.array([])
        
        show_progress = (
            show_progress if show_progress is not None
            else self.config.show_progress
        )
        
        logger.info(f"Encoding {len(texts)} texts...")
        
        embeddings = self.model.encode(
            texts,
            batch_size=self.config.batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=self.config.normalize
        )
        
        logger.info(f"✅ Generated embeddings: {embeddings.shape}")
        
        return embeddings
    
    def encode_chunks(
        self,
        chunks: List[Dict[str, Any]],
        text_field: str = "text"
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Encode chunk dictionaries to embeddings.
        
        Args:
            chunks: List of chunk dictionaries
            text_field: Field name containing text
            
        Returns:
            Tuple of (embeddings array, document IDs)
        """
        texts = [chunk.get(text_field, "") for chunk in chunks]
        doc_ids = [
            f"{chunk.get('document_id', 'unknown')}_{chunk.get('chunk_index', 0)}"
            for chunk in chunks
        ]
        
        embeddings = self.encode(texts)
        
        return embeddings, doc_ids
    
    def compute_similarity(
        self,
        embeddings1: np.ndarray,
        embeddings2: np.ndarray
    ) -> np.ndarray:
        """
        Compute cosine similarity between two sets of embeddings.
        
        Args:
            embeddings1: First set of embeddings (N x dim)
            embeddings2: Second set of embeddings (M x dim)
            
        Returns:
            Similarity matrix (N x M)
        """
        # Normalize if not already
        if not self.config.normalize:
            embeddings1 = embeddings1 / np.linalg.norm(
                embeddings1, axis=1, keepdims=True
            )
            embeddings2 = embeddings2 / np.linalg.norm(
                embeddings2, axis=1, keepdims=True
            )
        
        return np.dot(embeddings1, embeddings2.T)
    
    def find_similar(
        self,
        query_embedding: np.ndarray,
        corpus_embeddings: np.ndarray,
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Find most similar embeddings to a query.
        
        Args:
            query_embedding: Query embedding (1 x dim or dim,)
            corpus_embeddings: Corpus embeddings (N x dim)
            top_k: Number of top results
            
        Returns:
            List of (index, similarity) tuples
        """
        query_embedding = query_embedding.reshape(1, -1)
        similarities = self.compute_similarity(
            query_embedding, corpus_embeddings
        )[0]
        
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        return [(int(idx), float(similarities[idx])) for idx in top_indices]
    
    def save_embeddings(
        self,
        embeddings: np.ndarray,
        doc_ids: List[str],
        output_dir: Path
    ) -> Dict[str, str]:
        """
        Save embeddings and metadata to disk.
        
        Args:
            embeddings: Embeddings array
            doc_ids: Document IDs
            output_dir: Output directory
            
        Returns:
            Dictionary of output file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save embeddings
        embeddings_path = output_dir / "embeddings.npy"
        np.save(embeddings_path, embeddings)
        
        # Save document IDs
        ids_path = output_dir / "embedding_doc_ids.json"
        with open(ids_path, "w") as f:
            json.dump(doc_ids, f)
        
        # Save config
        config_path = output_dir / "embedding_config.json"
        with open(config_path, "w") as f:
            json.dump({
                "model_name": self.config.model_name,
                "embedding_dim": self.embedding_dim,
                "normalize": self.config.normalize,
                "num_embeddings": len(doc_ids)
            }, f, indent=2)
        
        logger.info(f"✅ Saved embeddings to {output_dir}")
        
        return {
            "embeddings": str(embeddings_path),
            "doc_ids": str(ids_path),
            "config": str(config_path)
        }
    
    @staticmethod
    def load_embeddings(
        output_dir: Path
    ) -> Tuple[np.ndarray, List[str], Dict[str, Any]]:
        """
        Load saved embeddings from disk.
        
        Args:
            output_dir: Directory containing saved embeddings
            
        Returns:
            Tuple of (embeddings, doc_ids, config)
        """
        output_dir = Path(output_dir)
        
        embeddings = np.load(output_dir / "embeddings.npy")
        
        with open(output_dir / "embedding_doc_ids.json", "r") as f:
            doc_ids = json.load(f)
        
        with open(output_dir / "embedding_config.json", "r") as f:
            config = json.load(f)
        
        logger.info(
            f"✅ Loaded {len(doc_ids)} embeddings "
            f"(dim={config.get('embedding_dim')})"
        )
        
        return embeddings, doc_ids, config


class MockEmbeddingExtractor:
    """
    Mock embedding extractor for testing without sentence-transformers.
    Generates random embeddings of the correct shape.
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self.embedding_dim = 384  # Mock dimension
        logger.warning("Using MockEmbeddingExtractor (random embeddings)")
    
    def encode(
        self,
        texts: List[str],
        show_progress: Optional[bool] = None
    ) -> np.ndarray:
        """Generate random embeddings."""
        embeddings = np.random.randn(len(texts), self.embedding_dim)
        if self.config.normalize:
            embeddings = embeddings / np.linalg.norm(
                embeddings, axis=1, keepdims=True
            )
        return embeddings
    
    def encode_chunks(
        self,
        chunks: List[Dict[str, Any]],
        text_field: str = "text"
    ) -> Tuple[np.ndarray, List[str]]:
        texts = [chunk.get(text_field, "") for chunk in chunks]
        doc_ids = [
            f"{chunk.get('document_id', 'unknown')}_{chunk.get('chunk_index', 0)}"
            for chunk in chunks
        ]
        return self.encode(texts), doc_ids


def create_extractor(
    config: Optional[EmbeddingConfig] = None,
    use_mock: bool = False
) -> Union[EmbeddingExtractor, MockEmbeddingExtractor]:
    """
    Factory function to create embedding extractor.
    
    Args:
        config: Optional embedding configuration
        use_mock: Force use of mock extractor
        
    Returns:
        Embedding extractor instance
    """
    if use_mock or not SENTENCE_TRANSFORMERS_AVAILABLE:
        return MockEmbeddingExtractor(config)
    
    return EmbeddingExtractor(config)


def extract_embeddings(
    chunks: List[Dict[str, Any]],
    config: Optional[EmbeddingConfig] = None,
    output_dir: Optional[Path] = None
) -> Tuple[np.ndarray, List[str]]:
    """
    Convenience function to extract embeddings from chunks.
    
    Args:
        chunks: List of chunk dictionaries
        config: Optional embedding configuration
        output_dir: Optional path to save embeddings
        
    Returns:
        Tuple of (embeddings array, document IDs)
    """
    extractor = create_extractor(config)
    embeddings, doc_ids = extractor.encode_chunks(chunks)
    
    if output_dir:
        if hasattr(extractor, 'save_embeddings'):
            extractor.save_embeddings(embeddings, doc_ids, output_dir)
        else:
            # For mock extractor
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            np.save(output_dir / "embeddings.npy", embeddings)
            with open(output_dir / "embedding_doc_ids.json", "w") as f:
                json.dump(doc_ids, f)
    
    return embeddings, doc_ids


def process_chunks_file(
    input_path: Path,
    output_dir: Path,
    config: Optional[EmbeddingConfig] = None
) -> Dict[str, Any]:
    """
    Process chunks file and extract embeddings.
    
    Args:
        input_path: Path to chunks JSON file
        output_dir: Directory to save outputs
        config: Optional embedding configuration
        
    Returns:
        Dictionary with results info
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load chunks
    logger.info(f"Loading chunks from {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    chunks = data.get("chunks", data)  # Handle both formats
    
    if not chunks:
        logger.warning("No chunks found in input file")
        return {"num_embeddings": 0, "embedding_dim": 0}
    
    logger.info(f"Loaded {len(chunks)} chunks for embedding extraction")
    
    # Extract embeddings
    extractor = create_extractor(config)
    embeddings, doc_ids = extractor.encode_chunks(chunks)
    
    # Save embeddings as NumPy array (binary format - much faster than JSON)
    embeddings_file = output_dir / "embeddings.npy"
    np.save(embeddings_file, embeddings)
    logger.info(f"✅ Saved embeddings to {embeddings_file}")
    
    # Save metadata separately as JSON
    metadata = {
        "model_name": config.model_name if config else "all-MiniLM-L6-v2",
        "num_chunks": len(chunks),
        "embedding_dim": int(extractor.embedding_dim),
        "chunk_ids": doc_ids
    }
    
    metadata_file = output_dir / "embedding_config.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"✅ Saved metadata to {metadata_file}")
    
    # Also save doc IDs separately for backward compatibility
    doc_ids_file = output_dir / "embedding_doc_ids.json"
    with open(doc_ids_file, "w", encoding="utf-8") as f:
        json.dump(doc_ids, f, indent=2)
    
    results = {
        "num_embeddings": len(embeddings),
        "embedding_dim": int(extractor.embedding_dim),
        "model": config.model_name if config else "all-MiniLM-L6-v2"
    }
    
    logger.info(f"📊 Embedding extraction complete: {embeddings.shape}")
    
    return results


# ---------------------------------
# RUN (Standalone execution)
# ---------------------------------

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    
    # Use default config
    config = EmbeddingConfig(
        model_name="all-MiniLM-L6-v2",
        batch_size=32,
        normalize=True
    )
    
    results = process_chunks_file(
        input_path=project_root / "data" / "processed" / "chunks.json",
        output_dir=project_root / "data" / "features" / "embeddings",
        config=config
    )
    
    print(f"\n✅ Embeddings Extracted")
    print(f"📊 Shape: {results['embeddings_shape']}")
    print(f"🧠 Model: {results['model_name']}")
