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

# Precompiled regexes for performance
HTML_TAG_REGEX = re.compile(r'<[^>]+>')
NON_WORD_SPACE_REGEX = re.compile(r'[^\w\s]')
WHITESPACE_REGEX = re.compile(r'\s+')


class ContentHashProcessor:
    """Processes the content_hash command: generate content hashes for similarity detection."""

    def __init__(self):
        """Initialize the content hash processor."""
        self.db = DatabaseConnection()
        self.norm_cache: Dict[int, str] = {}  # Cache for normalized content by articleId

    def execute(self):
        """
        Execute the content hash process:
        7. Populate contentHash (similarity 0-1 or 1/0 for exact) using SimHash/MinHash + SHA-1
        """
        print("Starting content hash process...")

        try:
            with self.db:
                # Get total count for progress tracking
                print("Getting total count of records to update...")
                count_records = self.db.get_analysis_records_for_content_hash_update()
                total_records = len(count_records)

                if total_records == 0:
                    print("No analysis records found to update")
                    return

                print(f"Found {total_records:,} analysis records to update")

                # Process records in batches using bulk query
                batch_size = 1000  # Increased batch size for better performance
                batch_updates = []
                processed_count = 0

                print("Processing content hash comparisons...")
                with tqdm(total=total_records, desc="Processing content", unit="records") as pbar:
                    while processed_count < total_records:
                        # Get batch of records with content included
                        records_batch = self.db.get_analysis_records_for_content_hash_update_with_contents(batch_size)

                        if not records_batch:
                            break

                        for record in records_batch:
                            # Perform content comparison using already-loaded content
                            content_similarity = self._compare_content_with_details(
                                record['headlineNew'], record['textNew'],
                                record['headlineApproved'], record['textApproved'],
                                record['articleIdNew'], record['articleIdApproved']
                            )

                            # Create update record
                            update_record = {
                                'id': record['id'],
                                'contentHash': content_similarity
                            }

                            batch_updates.append(update_record)
                            processed_count += 1

                        # Update batch
                        if batch_updates:
                            self._update_batch(batch_updates)
                            pbar.update(len(batch_updates))
                            batch_updates = []

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

        # Remove HTML tags if present (using precompiled regex)
        text = HTML_TAG_REGEX.sub(' ', text)

        # Remove special characters and extra whitespace (using precompiled regexes)
        text = NON_WORD_SPACE_REGEX.sub(' ', text)
        text = WHITESPACE_REGEX.sub(' ', text)

        # Remove common stop words for better similarity detection
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'
        }

        words = [word for word in text.split() if word not in stop_words and len(word) > 2]
        return ' '.join(words)

    def _prep_content(self, headline: Optional[str], text: Optional[str]) -> str:
        """
        Prepare content by normalizing and concatenating headline and text.
        Returns normalized string in format: "{norm(headline)}|||{norm(text)}"
        """
        norm_headline = self._normalize_text(headline) if headline else ""
        norm_text = self._normalize_text(text) if text else ""
        return f"{norm_headline}|||{norm_text}"

    def _sha1_from_normalized(self, normalized_content: str) -> str:
        """Generate SHA-1 hash from already normalized content."""
        if not normalized_content:
            return ""
        return hashlib.sha1(normalized_content.encode('utf-8')).hexdigest()

    def _simhash_from_normalized(self, normalized_content: str, hash_bits: int = 64) -> int:
        """
        Generate SimHash from already normalized content.
        Simple implementation without external dependencies.
        """
        if not normalized_content:
            return 0

        # Get words from already normalized content
        words = normalized_content.split()

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

    def _compare_content_with_details(self, headline_new: Optional[str], text_new: Optional[str],
                                    headline_approved: Optional[str], text_approved: Optional[str],
                                    article_id_new: int, article_id_approved: int) -> float:
        """
        Compare content using the optimized approach with caching and single normalization.
        Returns continuous similarity score from 0.0 to 1.0.
        """
        # Handle None cases
        if (headline_new is None and text_new is None) and (headline_approved is None and text_approved is None):
            return 1.0  # Both empty = exact match
        if (headline_new is None and text_new is None) or (headline_approved is None and text_approved is None):
            return 0.0  # One empty = no match

        # Get or compute normalized content with caching
        if article_id_new in self.norm_cache:
            norm1 = self.norm_cache[article_id_new]
        else:
            norm1 = self._prep_content(headline_new, text_new)
            self.norm_cache[article_id_new] = norm1

        if article_id_approved in self.norm_cache:
            norm2 = self.norm_cache[article_id_approved]
        else:
            norm2 = self._prep_content(headline_approved, text_approved)
            self.norm_cache[article_id_approved] = norm2

        # Check for exact match using SHA-1
        hash1 = self._sha1_from_normalized(norm1)
        hash2 = self._sha1_from_normalized(norm2)

        if hash1 == hash2 and hash1:  # Exact match
            return 1.0

        # Check for near-duplicate using SimHash
        simhash1 = self._simhash_from_normalized(norm1)
        simhash2 = self._simhash_from_normalized(norm2)

        if simhash1 == 0 and simhash2 == 0:  # Both empty after normalization
            return 0.0

        # Calculate similarity based on Hamming distance
        distance = self._hamming_distance(simhash1, simhash2)
        similarity = self._calculate_similarity(distance)

        return similarity  # Return continuous similarity score (0.0 to 1.0)

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
                print(f"Exact matches (1.0): {stats.get('exact_match_count', 0):,}")
                print(f"High similarity (0.85-0.99): {stats.get('high_similarity_count', 0):,}")
                print(f"Medium similarity (0.5-0.84): {stats.get('medium_similarity_count', 0):,}")
                print(f"Low similarity (0.01-0.49): {stats.get('low_similarity_count', 0):,}")
                print(f"No similarity (0.0): {stats.get('no_match_count', 0):,}")
                print("\nNext steps:")
                print("- Run 'python main.py embedding' to perform semantic analysis")
                print("="*50)
        except Exception as e:
            print(f"Could not generate detailed summary: {e}")
            print("="*50)