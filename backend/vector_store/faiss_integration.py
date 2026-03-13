"""
FAISS Integration Module
=========================

Handles creation, saving, loading, and querying of a FAISS index for similarity search.
"""

from __future__ import annotations

from pathlib import Path
import json
from typing import List, Dict, Any, Tuple

import faiss
import numpy as np

class FaissIndex:
    def __init__(self, dimension: int):
        """
        Initialize the FAISS index.

        Args:
            dimension: Dimensionality of the embeddings.
        """
        self.index = faiss.IndexFlatL2(dimension)

    def add_embeddings(self, embeddings: List[List[float]]) -> None:
        """
        Add embeddings to the FAISS index.

        Args:
            embeddings: List of embeddings to add.
        """
        np_embeddings = np.array(embeddings, dtype='float32')
        self.index.add(np_embeddings)

    def search(self, query_embedding: List[float], top_k: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Search the FAISS index for similar embeddings.

        Args:
            query_embedding: The embedding to search for.
            top_k: Number of top results to return.

        Returns:
            Distances and indices of the top_k results.
        """
        query = np.array([query_embedding], dtype='float32')
        distances, indices = self.index.search(query, top_k)
        return distances[0], indices[0]

    def save_index(self, file_path: str) -> None:
        """
        Save the FAISS index to a file.

        Args:
            file_path: Path to save the index file.
        """
        faiss.write_index(self.index, file_path)

    def load_index(self, file_path: str) -> None:
        """
        Load a FAISS index from a file.

        Args:
            file_path: Path to the index file.
        """
        self.index = faiss.read_index(file_path)


class FaissVectorStore:
    """
    Lightweight wrapper for a FAISS index with doc ID mapping.
    """

    def __init__(self, index: faiss.Index, doc_ids: List[str]):
        self.index = index
        self.doc_ids = doc_ids

    @property
    def size(self) -> int:
        return self.index.ntotal

    def save(self, output_dir: Path) -> Dict[str, str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        index_path = output_dir / "index.faiss"
        faiss.write_index(self.index, str(index_path))

        ids_path = output_dir / "doc_ids.json"
        with open(ids_path, "w", encoding="utf-8") as f:
            json.dump(self.doc_ids, f, indent=2)

        return {
            "index": str(index_path),
            "doc_ids": str(ids_path),
        }


def _load_embeddings(embeddings_dir: Path) -> Tuple[np.ndarray, List[str], Dict[str, Any]]:
    embeddings_dir = Path(embeddings_dir)

    embeddings_path = embeddings_dir / "embeddings.npy"
    doc_ids_path = embeddings_dir / "embedding_doc_ids.json"
    config_path = embeddings_dir / "embedding_config.json"

    embeddings = np.load(embeddings_path)
    with open(doc_ids_path, "r", encoding="utf-8") as f:
        doc_ids = json.load(f)

    config: Dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    return embeddings, doc_ids, config


def build_vector_store_from_embeddings(
    embeddings_dir: Path,
    chunks_path: Path,
    output_dir: Path
) -> FaissVectorStore:
    """
    Build a FAISS index from saved embeddings and persist index + metadata.
    """
    embeddings, doc_ids, config = _load_embeddings(embeddings_dir)

    if embeddings.size == 0:
        raise ValueError("No embeddings found to index.")

    dimension = int(embeddings.shape[1])
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype("float32"))

    store = FaissVectorStore(index=index, doc_ids=doc_ids)
    paths = store.save(output_dir)

    # Persist chunk metadata for retrieval
    chunks_path = Path(chunks_path)
    if chunks_path.exists():
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunk_data = json.load(f)
        chunks = chunk_data.get("chunks", chunk_data)
        chunk_meta_path = Path(output_dir) / "chunks.json"
        with open(chunk_meta_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

    # Save vector store metadata
    metadata = {
        "embedding_dim": dimension,
        "num_vectors": store.size,
        "model_name": config.get("model_name"),
        "normalize": config.get("normalize"),
        "index_path": paths.get("index"),
        "doc_ids_path": paths.get("doc_ids"),
        "chunks_path": str(Path(output_dir) / "chunks.json"),
    }
    with open(Path(output_dir) / "vector_store_meta.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return store

# Example usage
if __name__ == "__main__":
    dimension = 384  # Example dimension size for embeddings
    faiss_index = FaissIndex(dimension)

    # Example embeddings
    embeddings = [[0.1, 0.2, 0.3] * 128, [0.4, 0.5, 0.6] * 128]
    faiss_index.add_embeddings(embeddings)

    # Search
    query = [0.1, 0.2, 0.3] * 128
    distances, indices = faiss_index.search(query)
    print("Distances:", distances)
    print("Indices:", indices)

    # Save and load
    faiss_index.save_index("example.index")
    faiss_index.load_index("example.index")