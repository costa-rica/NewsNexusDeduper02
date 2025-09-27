"""
URL Check processor for NewsNexusDeduper02.
Handles step 6: URL canonicalization and exact URL matching.
"""

import re
from urllib.parse import urlparse, urlunparse
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from .database import DatabaseConnection


class UrlCheckProcessor:
    """Processes the url_check command: URL canonicalization and matching."""

    def __init__(self):
        """Initialize the URL check processor."""
        self.db = DatabaseConnection()

    def execute(self):
        """
        Execute the URL check process:
        6. Populate urlCheck (1 for match / 0 for no match) using URL canonicalization + exact URL match
        """
        print("Starting URL check process...")

        try:
            with self.db:
                # Get all analysis records that need URL checking
                print("Getting analysis records to update...")
                analysis_records = self.db.get_analysis_records_for_url_update()

                if not analysis_records:
                    print("No analysis records found to update")
                    return

                print(f"Found {len(analysis_records):,} analysis records to update")

                # Process records in batches
                batch_size = 1000
                batch_updates = []
                processed_count = 0

                print("Processing URL comparisons...")
                with tqdm(total=len(analysis_records), desc="Processing URLs", unit="records") as pbar:
                    for record in analysis_records:
                        # Get URLs for both articles
                        new_article_url = self.db.get_article_url(record['articleIdNew'])
                        approved_article_url = self.db.get_article_url(record['articleIdApproved'])

                        # Perform URL comparison
                        url_match = self._compare_urls(new_article_url, approved_article_url)

                        # Create update record
                        update_record = {
                            'id': record['id'],
                            'urlCheck': 1 if url_match else 0
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
            print(f"Error during URL check processing: {e}")
            return

    def _canonicalize_url(self, url: str) -> Optional[str]:
        """
        Canonicalize a URL for comparison.
        - Convert to lowercase
        - Remove www prefix
        - Remove trailing slashes
        - Remove common tracking parameters
        - Standardize protocol
        """
        if not url or not isinstance(url, str):
            return None

        try:
            # Parse the URL
            parsed = urlparse(url.strip().lower())

            # Skip invalid URLs
            if not parsed.netloc:
                return None

            # Remove www prefix
            netloc = parsed.netloc
            if netloc.startswith('www.'):
                netloc = netloc[4:]

            # Remove common tracking parameters
            query_params = []
            if parsed.query:
                params = parsed.query.split('&')
                tracking_params = {
                    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                    'fbclid', 'gclid', 'msclkid', 'mc_cid', 'mc_eid', '_ga', 'ref'
                }
                for param in params:
                    if '=' in param:
                        key = param.split('=')[0]
                        if key not in tracking_params:
                            query_params.append(param)

            # Remove trailing slash from path
            path = parsed.path.rstrip('/') if parsed.path != '/' else ''

            # Reconstruct canonical URL
            canonical = urlunparse((
                'https',  # Standardize to https
                netloc,
                path,
                parsed.params,
                '&'.join(query_params),
                ''  # Remove fragment
            ))

            return canonical

        except Exception:
            return None

    def _compare_urls(self, url1: Optional[str], url2: Optional[str]) -> bool:
        """
        Compare two URLs after canonicalization.
        Returns True if URLs match, False otherwise.
        """
        # Handle None cases
        if url1 is None and url2 is None:
            return True
        if url1 is None or url2 is None:
            return False

        # Canonicalize both URLs
        canonical1 = self._canonicalize_url(url1)
        canonical2 = self._canonicalize_url(url2)

        # Compare canonical URLs
        if canonical1 is None and canonical2 is None:
            return True
        if canonical1 is None or canonical2 is None:
            return False

        return canonical1 == canonical2

    def _update_batch(self, batch_updates: List[Dict[str, Any]]):
        """Update a batch of analysis records with URL check results."""
        if batch_updates:
            self.db.update_analysis_url_check_batch(batch_updates)

    def _print_summary(self, processed_count: int):
        """Print summary of the URL check process."""
        try:
            with self.db:
                # Get statistics
                stats = self.db.get_url_check_processing_stats()

                print("\n" + "="*50)
                print("URL CHECK PROCESS SUMMARY")
                print("="*50)
                print(f"Records processed: {processed_count:,}")
                print(f"URL matches found: {stats.get('url_match_count', 0):,}")
                print(f"URL non-matches: {stats.get('url_no_match_count', 0):,}")
                print("\nNext steps:")
                print("- Run 'python main.py content_hash' to generate content hashes")
                print("- Run 'python main.py embedding' to perform semantic analysis")
                print("="*50)
        except Exception as e:
            print(f"Could not generate detailed summary: {e}")
            print("="*50)