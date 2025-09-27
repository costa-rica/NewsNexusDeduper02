"""
Content Hash processor for NewsNexusDeduper02.
Handles step 7: Generate content hashes for similarity detection.
Uses SimHash for near-duplicate detection and SHA-1 for exact matches.
"""

import hashlib
import re
from typing import List, Dict, Any, Optional, Set
from tqdm import tqdm

from .database import DatabaseConnection


class ContentHashProcessor:
    """Processes the content_hash command: generate content hashes for similarity detection."""

    def __init__(self):
        """Initialize the content hash processor."""
        self.db = DatabaseConnection()

    def execute(self):
        """
        Execute the content hash process:
        7. Populate contentHash (similarity 0-1 or 1/0 for exact) using SimHash/MinHash + SHA-1
        """
        print("Starting content hash process...")

        try:
            with self.db:
                # Get all analysis records that need content hash checking
                print("Getting analysis records to update...")
                analysis_records = self.db.get_analysis_records_for_content_hash_update()

                if not analysis_records:
                    print("No analysis records found to update")
                    return

                print(f"Found {len(analysis_records):,} analysis records to update")

                # Process records in batches
                batch_size = 500  # Smaller batches for content processing
                batch_updates = []
                processed_count = 0

                print("Processing content hash comparisons...")
                with tqdm(total=len(analysis_records), desc="Processing content", unit="records") as pbar:
                    for record in analysis_records:
                        # Get content for both articles
                        new_article_content = self.db.get_article_content(record['articleIdNew'])
                        approved_article_content = self.db.get_article_content(record['articleIdApproved'])

                        # Perform content comparison
                        content_similarity = self._compare_content(new_article_content, approved_article_content)

                        # Create update record
                        update_record = {
                            'id': record['id'],
                            'contentHash': content_similarity
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
            print(f"Error during content hash processing: {e}")
            return

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.
        - Convert to lowercase
        - Remove extra whitespace
        - Remove special characters
        - Remove common stop words
        """
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove HTML tags if present
        text = re.sub(r'<[^>]+>', ' ', text)

        # Remove special characters and extra whitespace
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)

        # Remove common stop words for better similarity detection
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'
        }

        words = [word for word in text.split() if word not in stop_words and len(word) > 2]
        return ' '.join(words)

    def _generate_sha1_hash(self, text: str) -> str:
        """Generate SHA-1 hash for exact content matching."""
        if not text:
            return ""

        normalized = self._normalize_text(text)
        return hashlib.sha1(normalized.encode('utf-8')).hexdigest()

    def _generate_simhash(self, text: str, hash_bits: int = 64) -> int:
        """
        Generate SimHash for near-duplicate detection.
        Simple implementation without external dependencies.
        """
        if not text:
            return 0

        # Normalize text and get words
        normalized = self._normalize_text(text)
        words = normalized.split()

        if not words:
            return 0

        # Initialize bit vector
        bit_vector = [0] * hash_bits

        # Process each word
        for word in words:
            # Simple hash function for the word
            word_hash = hash(word) % (2 ** hash_bits)

            # Update bit vector based on word hash
            for i in range(hash_bits):
                if word_hash & (1 << i):
                    bit_vector[i] += 1
                else:
                    bit_vector[i] -= 1

        # Generate final hash
        simhash = 0
        for i in range(hash_bits):
            if bit_vector[i] > 0:
                simhash |= (1 << i)

        return simhash

    def _hamming_distance(self, hash1: int, hash2: int) -> int:
        """Calculate Hamming distance between two hash values."""
        return bin(hash1 ^ hash2).count('1')

    def _calculate_similarity(self, distance: int, total_bits: int = 64) -> float:
        """Convert Hamming distance to similarity score (0-1)."""
        return 1.0 - (distance / total_bits)

    def _compare_content(self, content1: Optional[str], content2: Optional[str]) -> int:
        """
        Compare two pieces of content and return similarity score.
        Returns 1 for exact match, 0 for no similarity, or similarity score scaled to 0-100.
        """
        # Handle None cases
        if content1 is None and content2 is None:
            return 1  # Both empty = exact match
        if content1 is None or content2 is None:
            return 0  # One empty = no match

        # Check for exact match using SHA-1
        hash1 = self._generate_sha1_hash(content1)
        hash2 = self._generate_sha1_hash(content2)

        if hash1 == hash2 and hash1:  # Exact match
            return 1

        # Check for near-duplicate using SimHash
        simhash1 = self._generate_simhash(content1)
        simhash2 = self._generate_simhash(content2)

        if simhash1 == 0 and simhash2 == 0:  # Both empty after normalization
            return 0

        # Calculate similarity based on Hamming distance
        distance = self._hamming_distance(simhash1, simhash2)
        similarity = self._calculate_similarity(distance)

        # Scale to 0-100 and round to integer
        # Consider high similarity (>0.85) as potential duplicate
        if similarity > 0.85:
            return 1  # High similarity = likely duplicate
        else:
            return 0  # Low similarity = likely not duplicate

    def _update_batch(self, batch_updates: List[Dict[str, Any]]):
        """Update a batch of analysis records with content hash results."""
        if batch_updates:
            self.db.update_analysis_content_hash_batch(batch_updates)

    def _print_summary(self, processed_count: int):
        """Print summary of the content hash process."""
        try:
            with self.db:
                # Get statistics
                stats = self.db.get_content_hash_processing_stats()

                print("\n" + "="*50)
                print("CONTENT HASH PROCESS SUMMARY")
                print("="*50)
                print(f"Records processed: {processed_count:,}")
                print(f"Content matches found: {stats.get('content_match_count', 0):,}")
                print(f"Content non-matches: {stats.get('content_no_match_count', 0):,}")
                print("\nNext steps:")
                print("- Run 'python main.py embedding' to perform semantic analysis")
                print("="*50)
        except Exception as e:
            print(f"Could not generate detailed summary: {e}")
            print("="*50)