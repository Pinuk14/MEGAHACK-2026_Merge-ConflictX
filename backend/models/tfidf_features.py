"""
TF-IDF Feature Extraction Module
================================

Implements TF-IDF vectorization using scikit-learn.
Pluggable extractor for traditional ML features.

Features:
- Configurable n-gram ranges
- Stop word filtering
- Max features control
- Batch processing support
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

# Attempt to import scikit-learn
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning(
        "scikit-learn not available. Install with: pip install scikit-learn"
    )


@dataclass
class TFIDFConfig:
    """Configuration for TF-IDF extraction."""
    max_features: int = 5000  # Maximum vocabulary size
    ngram_range: Tuple[int, int] = (1, 2)  # Unigrams and bigrams
    min_df: Union[int, float] = 2  # Minimum document frequency
    max_df: float = 0.95  # Maximum document frequency
    use_idf: bool = True  # Use inverse document frequency
    sublinear_tf: bool = True  # Apply sublinear TF scaling
    stop_words: str = "english"  # Stop words to remove
    lowercase: bool = True  # Convert to lowercase
    norm: str = "l2"  # Normalization method


class TFIDFExtractor:
    """
    Extracts TF-IDF features from text documents.
    
    Uses scikit-learn's TfidfVectorizer with configurable
    parameters for vocabulary control.
    
    Attributes:
        config: TFIDFConfig instance
        vectorizer: Fitted TfidfVectorizer
        vocabulary_: Learned vocabulary
    """
    
    def __init__(self, config: Optional[TFIDFConfig] = None):
        """
        Initialize the TF-IDF extractor.
        
        Args:
            config: Optional TF-IDF configuration
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError(
                "scikit-learn is required for TF-IDF extraction. "
                "Install with: pip install scikit-learn"
            )
        
        self.config = config or TFIDFConfig()
        self.vectorizer = self._create_vectorizer()
        self.vocabulary_ = None
        self._is_fitted = False
    
    def _create_vectorizer(self) -> TfidfVectorizer:
        """
        Create TfidfVectorizer with config settings.
        
        Returns:
            Configured TfidfVectorizer
        """
        return TfidfVectorizer(
            max_features=self.config.max_features,
            ngram_range=self.config.ngram_range,
            min_df=self.config.min_df,
            max_df=self.config.max_df,
            use_idf=self.config.use_idf,
            sublinear_tf=self.config.sublinear_tf,
            stop_words=self.config.stop_words,
            lowercase=self.config.lowercase,
            norm=self.config.norm
        )
    
    def fit(self, texts: List[str]) -> "TFIDFExtractor":
        """
        Fit the vectorizer on a corpus of texts.
        
        Args:
            texts: List of text documents
            
        Returns:
            Self for method chaining
        """
        logger.info(f"Fitting TF-IDF vectorizer on {len(texts)} documents...")
        
        self.vectorizer.fit(texts)
        self.vocabulary_ = self.vectorizer.vocabulary_
        self._is_fitted = True
        
        logger.info(f"✅ Vocabulary size: {len(self.vocabulary_)}")
        
        return self
    
    def transform(self, texts: List[str]) -> np.ndarray:
        """
        Transform texts to TF-IDF vectors.
        
        Args:
            texts: List of text documents
            
        Returns:
            TF-IDF matrix (sparse or dense)
        """
        if not self._is_fitted:
            raise ValueError("Vectorizer must be fitted before transform")
        
        return self.vectorizer.transform(texts)
    
    def fit_transform(self, texts: List[str]) -> np.ndarray:
        """
        Fit and transform in one step.
        
        Args:
            texts: List of text documents
            
        Returns:
            TF-IDF matrix
        """
        logger.info(f"Fit-transforming TF-IDF on {len(texts)} documents...")
        
        logger.debug(f"Input texts for TF-IDF: {texts}")  # Debug log to inspect input texts
        
        tfidf_matrix = self.vectorizer.fit_transform(texts)
        self.vocabulary_ = self.vectorizer.vocabulary_
        self._is_fitted = True
        
        logger.info(
            f"✅ TF-IDF matrix shape: {tfidf_matrix.shape}, "
            f"vocabulary size: {len(self.vocabulary_)}"
        )
        
        return tfidf_matrix
    
    def extract_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
        text_field: str = "text"
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Extract TF-IDF features from chunk dictionaries.
        
        Args:
            chunks: List of chunk dictionaries
            text_field: Field name containing text
            
        Returns:
            Tuple of (TF-IDF matrix, document IDs)
        """
        texts = [chunk.get(text_field, "") for chunk in chunks]
        doc_ids = [
            f"{chunk.get('document_id', 'unknown')}_{chunk.get('chunk_index', 0)}"
            for chunk in chunks
        ]
        
        tfidf_matrix = self.fit_transform(texts)
        
        return tfidf_matrix, doc_ids
    
    def get_feature_names(self) -> List[str]:
        """
        Get the feature names (vocabulary terms).
        
        Returns:
            List of feature names
        """
        if not self._is_fitted:
            return []
        return self.vectorizer.get_feature_names_out().tolist()
    
    def get_top_terms(
        self,
        tfidf_vector: np.ndarray,
        top_n: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Get top TF-IDF terms for a single document.
        
        Args:
            tfidf_vector: TF-IDF vector for one document
            top_n: Number of top terms to return
            
        Returns:
            List of (term, score) tuples
        """
        feature_names = self.get_feature_names()
        
        # Handle sparse matrix
        if hasattr(tfidf_vector, "toarray"):
            tfidf_vector = tfidf_vector.toarray().flatten()
        elif len(tfidf_vector.shape) > 1:
            tfidf_vector = tfidf_vector.flatten()
        
        # Get top indices
        top_indices = np.argsort(tfidf_vector)[-top_n:][::-1]
        
        return [
            (feature_names[i], float(tfidf_vector[i]))
            for i in top_indices
            if tfidf_vector[i] > 0
        ]
    
    def save(self, path: Path) -> None:
        """
        Save the fitted vectorizer to disk.
        
        Args:
            path: Path to save the vectorizer
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "wb") as f:
            pickle.dump({
                "vectorizer": self.vectorizer,
                "config": self.config,
                "vocabulary": self.vocabulary_
            }, f)
        
        logger.info(f"✅ Saved TF-IDF vectorizer to {path}")
    
    @classmethod
    def load(cls, path: Path) -> "TFIDFExtractor":
        """
        Load a fitted vectorizer from disk.
        
        Args:
            path: Path to the saved vectorizer
            
        Returns:
            Loaded TFIDFExtractor
        """
        with open(path, "rb") as f:
            data = pickle.load(f)
        
        extractor = cls(data.get("config"))
        extractor.vectorizer = data["vectorizer"]
        extractor.vocabulary_ = data.get("vocabulary")
        extractor._is_fitted = True
        
        logger.info(f"✅ Loaded TF-IDF vectorizer from {path}")
        return extractor


def extract_tfidf_features(
    chunks: List[Dict[str, Any]],
    config: Optional[TFIDFConfig] = None,
    output_path: Optional[Path] = None
) -> Tuple[np.ndarray, List[str], TFIDFExtractor]:
    """
    Convenience function to extract TF-IDF features from chunks.
    
    Args:
        chunks: List of chunk dictionaries
        config: Optional TF-IDF configuration
        output_path: Optional path to save vectorizer
        
    Returns:
        Tuple of (TF-IDF matrix, document IDs, extractor)
    """
    extractor = TFIDFExtractor(config)
    tfidf_matrix, doc_ids = extractor.extract_from_chunks(chunks)
    
    if output_path:
        extractor.save(output_path)
    
    return tfidf_matrix, doc_ids, extractor


def process_chunks_file(
    input_path: Path,
    output_dir: Path,
    config: Optional[TFIDFConfig] = None
) -> Dict[str, Any]:
    """
    Process chunks file and extract TF-IDF features.
    
    Args:
        input_path: Path to chunks JSON file
        output_dir: Directory to save outputs
        config: Optional TF-IDF configuration
        
    Returns:
        Dictionary with results info
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load chunks
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    chunks = data.get("chunks", data)  # Handle both formats
    logger.info(f"Loaded {len(chunks)} chunks for TF-IDF extraction")
    
    # Extract features
    tfidf_matrix, doc_ids, extractor = extract_tfidf_features(
        chunks,
        config,
        output_dir / "tfidf_vectorizer.pkl"
    )
    
    # Save matrix (as dense numpy for smaller datasets)
    if tfidf_matrix.shape[0] * tfidf_matrix.shape[1] < 1e8:
        np.save(
            output_dir / "tfidf_matrix.npy",
            tfidf_matrix.toarray()
        )
    else:
        # Save as sparse for large datasets
        from scipy import sparse
        sparse.save_npz(output_dir / "tfidf_matrix.npz", tfidf_matrix)
    
    # Save document IDs mapping
    with open(output_dir / "tfidf_doc_ids.json", "w") as f:
        json.dump(doc_ids, f)
    
    # Generate sample top terms for first few chunks
    sample_top_terms = {}
    for i, chunk in enumerate(chunks[:5]):
        top_terms = extractor.get_top_terms(tfidf_matrix[i], top_n=5)
        sample_top_terms[doc_ids[i]] = top_terms
    
    results = {
        "matrix_shape": list(tfidf_matrix.shape),
        "vocabulary_size": len(extractor.vocabulary_),
        "num_documents": len(doc_ids),
        "sample_top_terms": sample_top_terms,
        "output_files": [
            str(output_dir / "tfidf_vectorizer.pkl"),
            str(output_dir / "tfidf_matrix.npy"),
            str(output_dir / "tfidf_doc_ids.json")
        ]
    }
    
    logger.info(f"✅ TF-IDF extraction complete: {tfidf_matrix.shape}")
    
    return results


# ---------------------------------
# RUN (Standalone execution)
# ---------------------------------

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    
    results = process_chunks_file(
        input_path=project_root / "data" / "processed" / "chunks.json",
        output_dir=project_root / "data" / "features" / "tfidf"
    )
    
    print(f"\n✅ TF-IDF Features Extracted")
    print(f"📊 Matrix shape: {results['matrix_shape']}")
    print(f"📚 Vocabulary size: {results['vocabulary_size']}")
