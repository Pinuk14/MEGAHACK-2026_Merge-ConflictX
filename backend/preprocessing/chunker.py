"""
Text Chunking Module
====================

Chunks Original_content for embedding/vectorization.
Implements overlapping windows for semantic continuity.

Features:
- Configurable chunk sizes
- Overlapping windows
- Sentence-aware splitting
- Metadata preservation per chunk
"""

from pathlib import Path
import json
import re
from typing import List, Dict, Any, Optional, Iterator, Tuple
from dataclasses import dataclass, field
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """Configuration for text chunking."""
    chunk_size: int = 512  # Target chunk size in characters
    chunk_overlap: int = 50  # Overlap between chunks
    min_chunk_size: int = 100  # Minimum chunk size
    max_chunk_size: int = 1024  # Maximum chunk size
    sentence_aware: bool = True  # Try to break at sentence boundaries
    preserve_paragraphs: bool = True  # Try to preserve paragraph structure


@dataclass
class Chunk:
    """
    Represents a single text chunk with metadata.
    """
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    document_id: str
    document_title: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary."""
        return {
            "text": self.text,
            "chunk_index": self.chunk_index,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "source": self.source,
            "char_count": len(self.text),
            "metadata": self.metadata
        }


class TextChunker:
    """
    Chunks text documents with overlapping windows.
    
    Designed for preparing text for embedding models with
    configurable chunk sizes and overlap.
    
    Attributes:
        config: ChunkingConfig instance
    """
    
    # Sentence-ending patterns
    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')
    PARAGRAPH_BREAKS = re.compile(r'\n\s*\n')
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        """
        Initialize the text chunker.
        
        Args:
            config: Optional chunking configuration
        """
        self.config = config or ChunkingConfig()
        
    def _find_sentence_boundary(
        self,
        text: str,
        target_pos: int,
        search_range: int = 100
    ) -> int:
        """
        Find the nearest sentence boundary to target position.
        
        Args:
            text: The text to search in
            target_pos: Target position
            search_range: Range to search for boundary
            
        Returns:
            Position of nearest sentence boundary
        """
        if not self.config.sentence_aware:
            return target_pos
        
        # Search backward for sentence ending
        start_search = max(0, target_pos - search_range)
        end_search = min(len(text), target_pos + search_range)
        search_text = text[start_search:end_search]
        
        # Find all sentence endings in range
        endings = list(self.SENTENCE_ENDINGS.finditer(search_text))
        
        if not endings:
            return target_pos
        
        # Find ending closest to target
        relative_target = target_pos - start_search
        best_ending = min(
            endings,
            key=lambda m: abs(m.end() - relative_target)
        )
        
        return start_search + best_ending.end()
    
    def _split_into_paragraphs(self, text: str) -> List[Tuple[str, int]]:
        """
        Split text into paragraphs with their starting positions.
        
        Args:
            text: Text to split
            
        Returns:
            List of (paragraph_text, start_position) tuples
        """
        paragraphs = []
        current_pos = 0
        
        for match in self.PARAGRAPH_BREAKS.finditer(text):
            para_text = text[current_pos:match.start()].strip()
            if para_text:
                paragraphs.append((para_text, current_pos))
            current_pos = match.end()
        
        # Don't forget the last paragraph
        remaining = text[current_pos:].strip()
        if remaining:
            paragraphs.append((remaining, current_pos))
        
        return paragraphs if paragraphs else [(text, 0)]
    
    def chunk_text(
        self,
        text: str,
        document_id: str = "",
        document_title: str = "",
        source: str = "",
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk a single text document.
        
        Args:
            text: Text to chunk
            document_id: Unique document identifier
            document_title: Document title
            source: Document source type
            extra_metadata: Additional metadata to include
            
        Returns:
            List of Chunk objects
        """
        if not text or len(text) < self.config.min_chunk_size:
            # Return single chunk for small documents
            if text:
                return [Chunk(
                    text=text,
                    chunk_index=0,
                    start_char=0,
                    end_char=len(text),
                    document_id=document_id,
                    document_title=document_title,
                    source=source,
                    metadata=extra_metadata or {}
                )]
            return []
        
        chunks = []
        current_pos = 0
        chunk_index = 0
        
        while current_pos < len(text):
            # Calculate end position
            end_pos = current_pos + self.config.chunk_size
            
            # Don't exceed text length
            if end_pos >= len(text):
                end_pos = len(text)
            else:
                # Find sentence boundary
                end_pos = self._find_sentence_boundary(text, end_pos)
                
                # Ensure we don't exceed max chunk size
                if end_pos - current_pos > self.config.max_chunk_size:
                    end_pos = current_pos + self.config.max_chunk_size
            
            # Extract chunk text
            chunk_text = text[current_pos:end_pos].strip()
            
            # Only add if meets minimum size
            if len(chunk_text) >= self.config.min_chunk_size or end_pos >= len(text):
                chunks.append(Chunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    start_char=current_pos,
                    end_char=end_pos,
                    document_id=document_id,
                    document_title=document_title,
                    source=source,
                    metadata=extra_metadata or {}
                ))
                chunk_index += 1
            
            # Move to next position with overlap
            current_pos = end_pos - self.config.chunk_overlap
            
            # Prevent infinite loop
            if current_pos <= chunks[-1].start_char if chunks else 0:
                current_pos = end_pos
        
        return chunks
    
    def chunk_document(self, record: Dict[str, Any]) -> List[Chunk]:
        """
        Chunk a document record.
        
        Args:
            record: Document record with Original_content
            
        Returns:
            List of Chunk objects
        """
        text = record.get("Original_content", "")
        
        # Create document ID from title and source
        doc_id = f"{record.get('source', 'unknown')}_{record.get('title', 'untitled')}"
        
        # Extract relevant metadata
        extra_metadata = {
            "Published_date": record.get("Published_date"),
            "Type": record.get("Metadata", {}).get("Type"),
            "Accuracy": record.get("Metadata", {}).get("Accuracy")
        }
        
        return self.chunk_text(
            text=text,
            document_id=doc_id,
            document_title=record.get("title", "Untitled"),
            source=record.get("source", "unknown"),
            extra_metadata=extra_metadata
        )
    
    def chunk_all(
        self,
        records: List[Dict[str, Any]]
    ) -> Tuple[List[Chunk], Dict[str, Any]]:
        """
        Chunk all documents in a record list.
        
        Args:
            records: List of document records
            
        Returns:
            Tuple of (all_chunks, statistics)
        """
        all_chunks = []
        doc_chunk_counts = {}
        
        for record in records:
            chunks = self.chunk_document(record)
            all_chunks.extend(chunks)
            
            doc_id = f"{record.get('source', 'unknown')}_{record.get('title', 'untitled')}"
            doc_chunk_counts[doc_id] = len(chunks)
        
        statistics = {
            "total_chunks": len(all_chunks),
            "total_documents": len(records),
            "avg_chunks_per_doc": len(all_chunks) / len(records) if records else 0,
            "avg_chunk_size": (
                sum(len(c.text) for c in all_chunks) / len(all_chunks)
                if all_chunks else 0
            ),
            "chunk_config": {
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
                "sentence_aware": self.config.sentence_aware
            }
        }
        
        logger.info(
            f"✅ Created {len(all_chunks)} chunks from {len(records)} documents "
            f"(avg {statistics['avg_chunks_per_doc']:.1f} chunks/doc)"
        )
        
        return all_chunks, statistics


def chunk_documents(
    records: List[Dict[str, Any]],
    config: Optional[ChunkingConfig] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Convenience function to chunk documents.
    
    Args:
        records: List of document records
        config: Optional chunking configuration
        
    Returns:
        Tuple of (chunk_dicts, statistics)
    """
    chunker = TextChunker(config)
    chunks, stats = chunker.chunk_all(records)
    
    # Convert to dictionaries
    chunk_dicts = [c.to_dict() for c in chunks]
    
    return chunk_dicts, stats


def chunk_and_save(
    input_path: Path,
    output_path: Path,
    config: Optional[ChunkingConfig] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Load documents, chunk them, and save results.
    
    Args:
        input_path: Path to enriched JSON file
        output_path: Path to save chunks JSON
        config: Optional chunking configuration
        
    Returns:
        Tuple of (chunks, statistics)
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    # Load records
    with open(input_path, "r", encoding="utf-8") as f:
        records = json.load(f)
    
    logger.info(f"Loaded {len(records)} records for chunking")
    
    # Chunk documents
    chunks, stats = chunk_documents(records, config)
    
    # Save chunks
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    output_data = {
        "chunks": chunks,
        "statistics": stats
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Saved {len(chunks)} chunks to {output_path}")
    
    return chunks, stats


# ---------------------------------
# RUN (Standalone execution)
# ---------------------------------

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    
    # Use custom config for demonstration
    config = ChunkingConfig(
        chunk_size=512,
        chunk_overlap=50,
        sentence_aware=True
    )
    
    chunks, stats = chunk_and_save(
        input_path=project_root / "data" / "processed" / "final_enriched.json",
        output_path=project_root / "data" / "processed" / "chunks.json",
        config=config
    )
    
    print(f"\n✅ Created {len(chunks)} chunks")
    print(f"📊 Statistics: {json.dumps(stats, indent=2)}")
