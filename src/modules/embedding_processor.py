"""
Embedding processor for NewsNexusDeduper02.
Handles step 8: Perform semantic similarity analysis using embeddings.
Uses sentence-transformers with all-MiniLM-L6-v2 model and cosine similarity.
"""

import re
import numpy as np
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from .database import DatabaseConnection

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

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required for embedding processing. "
                "Install it with: pip install sentence-transformers"
            )

    def _load_model(self):
        """Load the sentence transformer model."""
        if self.model is None:
            print("Loading all-MiniLM-L6-v2 model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            print("Model loaded successfully")

    def execute(self):
        """
        Execute the embedding process:
        8. Populate embeddingSearch (cosine similarity 0-1) using all-MiniLM-L6-v2 embeddings
        """
        print("Starting embedding process...")

        # Load the model first
        self._load_model()

        try:
            with self.db:
                # Get all analysis records that need embedding analysis
                print("Getting analysis records to update...")
                analysis_records = self.db.get_analysis_records_for_embedding_update()

                if not analysis_records:
                    print("No analysis records found to update")
                    return

                print(f"Found {len(analysis_records):,} analysis records to update")

                # Process records in batches
                batch_size = 100  # Smaller batches for embedding processing
                batch_updates = []
                processed_count = 0

                print("Processing semantic similarity analysis...")
                with tqdm(total=len(analysis_records), desc="Processing embeddings", unit="records") as pbar:
                    for record in analysis_records:
                        # Get content for both articles
                        new_article_content = self.db.get_article_content(record['articleIdNew'])
                        approved_article_content = self.db.get_article_content(record['articleIdApproved'])

                        # Perform semantic similarity analysis
                        similarity_score = self._calculate_semantic_similarity(
                            new_article_content,
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
                            pbar.update(len(batch_updates))
                            batch_updates = []

                    # Process remaining updates
                    if batch_updates:
                        self._update_batch(batch_updates)
                        pbar.update(len(batch_updates))

                print(f"Successfully processed {processed_count:,} records")
                self._print_summary(processed_count)

        except Exception as e:
            print(f"Error during embedding processing: {e}")
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

    def _calculate_semantic_similarity(self, content1: Optional[str], content2: Optional[str]) -> int:
        """
        Calculate semantic similarity between two pieces of content using embeddings.
        Returns similarity score as integer (0 or 1 for duplicate detection).
        """
        # Handle None cases
        if content1 is None and content2 is None:
            return 1  # Both empty = similar
        if content1 is None or content2 is None:
            return 0  # One empty = not similar

        # Preprocess content
        processed_content1 = self._preprocess_text(content1)
        processed_content2 = self._preprocess_text(content2)

        # Handle empty content after preprocessing
        if not processed_content1 and not processed_content2:
            return 1  # Both empty after processing = similar
        if not processed_content1 or not processed_content2:
            return 0  # One empty after processing = not similar

        try:
            # Generate embeddings
            embeddings = self.model.encode([processed_content1, processed_content2])
            embedding1 = embeddings[0]
            embedding2 = embeddings[1]

            # Calculate cosine similarity
            cosine_similarity = self._cosine_similarity(embedding1, embedding2)

            # Convert to binary decision based on threshold
            # Consider high similarity (>0.8) as potential semantic duplicate
            if cosine_similarity > 0.8:
                return 1  # High semantic similarity = likely duplicate
            else:
                return 0  # Low semantic similarity = likely not duplicate

        except Exception as e:
            print(f"Error calculating similarity: {e}")
            return 0  # Default to no similarity on error

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        # Normalize vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calculate cosine similarity
        similarity = np.dot(vec1, vec2) / (norm1 * norm2)

        # Ensure result is between 0 and 1
        return max(0.0, min(1.0, float(similarity)))

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

                print("\n" + "="*50)
                print("EMBEDDING PROCESS SUMMARY")
                print("="*50)
                print(f"Records processed: {processed_count:,}")
                print(f"Semantic matches found: {stats.get('embedding_match_count', 0):,}")
                print(f"Semantic non-matches: {stats.get('embedding_no_match_count', 0):,}")
                print("\nAll processing steps completed!")
                print("Use the analysis results to identify potential duplicates.")
                print("="*50)
        except Exception as e:
            print(f"Could not generate detailed summary: {e}")
            print("="*50)