"""
Embedding processor for NewsNexusDeduper02.
Handles step 8: Perform semantic similarity analysis using embeddings.
Uses sentence-transformers with all-MiniLM-L6-v2 model and cosine similarity.
"""

import re
import numpy as np
from typing import List, Dict, Any, Optional

from .database import DatabaseConnection
from .logger import get_logger

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class EmbeddingProcessor:
    """Processes the embedding command: semantic similarity analysis using embeddings."""

    def __init__(self):
        """Initialize the embedding processor."""
        self.db = DatabaseConnection()
        self.model = None
        self.embedding_cache: Dict[int, np.ndarray] = {}
        self.logger = get_logger(__name__)

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required for embedding processing. "
                "Install it with: pip install sentence-transformers"
            )

    def _load_model(self):
        """Load the sentence transformer model."""
        if self.model is None:
            self.logger.info("Loading sentence-transformers/all-MiniLM-L6-v2 model...")
            self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            self.model.max_seq_length = 256
            self.logger.info("Model loaded successfully")

    def execute(self):
        """
        Execute the embedding process:
        8. Populate embeddingSearch (cosine similarity 0-1) using all-MiniLM-L6-v2 embeddings
        """
        self.logger.info("Starting embedding process...")

        # Load the model first
        self._load_model()

        try:
            with self.db:
                # Get all analysis records that need embedding analysis
                self.logger.info("Getting analysis records to update...")
                analysis_records = self.db.get_analysis_records_for_embedding_update()

                if not analysis_records:
                    self.logger.warning("No analysis records found to update")
                    return

                total = len(analysis_records)
                self.logger.info(f"Found {total:,} analysis records to update")

                # Process records in batches
                batch_size = 100  # Smaller batches for embedding processing
                batch_updates = []
                processed_count = 0
                next_log_threshold = 0.1  # 10%

                self.logger.info("Processing semantic similarity analysis...")

                for i, record in enumerate(analysis_records, 1):
                    # Get content for both articles
                    new_article_content = self.db.get_article_content(record['articleIdNew'])
                    approved_article_content = self.db.get_article_content(record['articleIdApproved'])

                    # Perform semantic similarity analysis
                    similarity_score = self._calculate_semantic_similarity(
                        record['articleIdNew'],
                        new_article_content,
                        record['articleIdApproved'],
                        approved_article_content
                    )

                    # Create update record
                    update_record = {
                        'id': record['id'],
                        'embeddingSearch': similarity_score
                    }

                    batch_updates.append(update_record)
                    processed_count += 1

                    # Process batch when it reaches batch_size
                    if len(batch_updates) >= batch_size:
                        self._update_batch(batch_updates)
                        batch_updates = []

                    # Log progress at 10% intervals
                    if total > 0:
                        ratio = i / total
                        if ratio >= next_log_threshold or i == total:
                            percent = int(ratio * 100)
                            self.logger.info(f"Processing embeddings: {percent}% ({i:,}/{total:,})")
                            next_log_threshold += 0.1

                # Process remaining updates
                if batch_updates:
                    self._update_batch(batch_updates)

                self.logger.info(f"Successfully processed {processed_count:,} records")
                self._print_summary(processed_count)

        except Exception as e:
            self.logger.error(f"Error during embedding processing: {e}")
            return

    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text for embedding generation.
        - Remove HTML tags
        - Normalize whitespace
        - Truncate to reasonable length for embedding model
        """
        if not text:
            return ""

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Truncate to avoid token limits (all-MiniLM-L6-v2 has 256 token limit)
        # Roughly 4 characters per token, so limit to ~1000 characters
        if len(text) > 1000:
            text = text[:1000]

        return text

    def _get_or_compute_embedding(self, article_id: int, raw_text: Optional[str]) -> np.ndarray:
        """
        Get cached embedding or compute and cache it for the given article.

        Args:
            article_id: The article ID for caching
            raw_text: The raw text content to embed

        Returns:
            The embedding vector as numpy array
        """
        # Check cache first
        if article_id in self.embedding_cache:
            return self.embedding_cache[article_id]

        # Preprocess text
        processed_text = self._preprocess_text(raw_text) if raw_text else ""

        # Handle empty content
        if not processed_text:
            # Return zero vector with correct dimensions
            embedding_dim = self.model.get_sentence_embedding_dimension()
            zero_embedding = np.zeros(embedding_dim, dtype=np.float32)
            self.embedding_cache[article_id] = zero_embedding
            return zero_embedding

        # Compute embedding
        embedding = self.model.encode(
            [processed_text],
            normalize_embeddings=True,
            convert_to_numpy=True
        )[0]

        # Cache and return
        self.embedding_cache[article_id] = embedding
        return embedding

    def _calculate_semantic_similarity(self, article_id1: int, content1: Optional[str],
                                     article_id2: int, content2: Optional[str]) -> float:
        """
        Calculate semantic similarity between two pieces of content using embeddings.
        Returns cosine similarity score as float (0.0-1.0).
        """
        # Handle None cases
        if content1 is None and content2 is None:
            return 1.0  # Both empty = perfectly similar
        if content1 is None or content2 is None:
            return 0.0  # One empty = not similar

        try:
            # Get embeddings using cache
            embedding1 = self._get_or_compute_embedding(article_id1, content1)
            embedding2 = self._get_or_compute_embedding(article_id2, content2)

            # Calculate cosine similarity (dot product for normalized vectors)
            cosine_similarity = float(np.dot(embedding1, embedding2))

            # Ensure result is between 0 and 1
            return max(0.0, min(1.0, cosine_similarity))

        except Exception as e:
            self.logger.error(f"Error calculating similarity: {e}")
            return 0.0  # Default to no similarity on error

    def _update_batch(self, batch_updates: List[Dict[str, Any]]):
        """Update a batch of analysis records with embedding results."""
        if batch_updates:
            self.db.update_analysis_embedding_batch(batch_updates)

    def _print_summary(self, processed_count: int):
        """Print summary of the embedding process."""
        try:
            with self.db:
                # Get statistics
                stats = self.db.get_embedding_processing_stats()

                self.logger.info("=" * 50)
                self.logger.info("EMBEDDING PROCESS SUMMARY")
                self.logger.info("=" * 50)
                self.logger.info(f"Records processed: {processed_count:,}")
                self.logger.info(f"High similarity (>0.8): {stats.get('high_similarity_count', 0):,}")
                self.logger.info(f"Medium similarity (0.5-0.8): {stats.get('medium_similarity_count', 0):,}")
                self.logger.info(f"Low similarity (<0.5): {stats.get('low_similarity_count', 0):,}")
                self.logger.info(f"Total with similarity scores: {stats.get('processed_count', 0):,}")
                self.logger.info(f"Unique articles cached: {len(self.embedding_cache):,}")
                self.logger.info("\nAll processing steps completed!")
                self.logger.info("Use the analysis results to identify potential duplicates.")
                self.logger.info("=" * 50)
        except Exception as e:
            self.logger.error(f"Could not generate detailed summary: {e}")
            self.logger.info("=" * 50)