"""
States processor for NewsNexusDeduper02.
Handles steps 3-5: Populate state information and state matching flags.
"""

import os
from typing import List, Dict, Any

from .database import DatabaseConnection
from .logger import get_logger


class StatesProcessor:
    """Processes the states command: populate state information and matching flags."""

    def __init__(self):
        """Initialize the states processor."""
        self.db = DatabaseConnection()
        self.logger = get_logger(__name__)
        self.use_tqdm = os.getenv("RUN_ENVIRONMENT", "production").lower() == "workstation"

    def execute(self):
        """
        Execute the states process:
        3. Populate articleNewState using relationship between Article, ArticleStateContract, and State
        4. Populate articleApprovedState using the same relationship
        5. Populate sameStateFlag (1 if states match, 0 otherwise)
        """
        self.logger.info("Starting states process...")

        try:
            with self.db:
                # Get all analysis records that need state information
                self.logger.info("Getting analysis records to update...")
                analysis_records = self.db.get_analysis_records_for_state_update()

                if not analysis_records:
                    self.logger.warning("No analysis records found to update")
                    return

                total = len(analysis_records)
                self.logger.info(f"Found {total:,} analysis records to update")

                # Process records in batches
                batch_size = 1000
                batch_updates = []
                processed_count = 0
                next_log_threshold = 0.1  # 10%

                self.logger.info("Processing state information...")

                # Setup progress tracking based on environment
                if self.use_tqdm:
                    from tqdm import tqdm
                    progress_iter = tqdm(analysis_records, desc="Processing states", unit="records")
                else:
                    progress_iter = analysis_records

                for i, record in enumerate(progress_iter, 1):
                    # Get state for new article
                    new_article_state = self.db.get_article_state(record['articleIdNew'])

                    # Get state for approved article
                    approved_article_state = self.db.get_article_state(record['articleIdApproved'])

                    # Determine if states match
                    same_state_flag = 1 if new_article_state == approved_article_state else 0

                    # Create update record
                    update_record = {
                        'id': record['id'],
                        'articleNewState': new_article_state or '',
                        'articleApprovedState': approved_article_state or '',
                        'sameStateFlag': same_state_flag
                    }

                    batch_updates.append(update_record)
                    processed_count += 1

                    # Process batch when it reaches batch_size
                    if len(batch_updates) >= batch_size:
                        self._update_batch(batch_updates)
                        batch_updates = []

                    # Log progress for server environment
                    if not self.use_tqdm and total > 0:
                        ratio = i / total
                        if ratio >= next_log_threshold or i == total:
                            percent = int(ratio * 100)
                            self.logger.info(f"Processing states: {percent}% ({i:,}/{total:,})")
                            next_log_threshold += 0.1

                # Process remaining updates
                if batch_updates:
                    self._update_batch(batch_updates)

                self.logger.info(f"Successfully processed {processed_count:,} records")
                self._print_summary(processed_count)

        except Exception as e:
            self.logger.error(f"Error during states processing: {e}")
            return

    def _update_batch(self, batch_updates: List[Dict[str, Any]]):
        """Update a batch of analysis records with state information."""
        if batch_updates:
            self.db.update_analysis_states_batch(batch_updates)

    def _print_summary(self, processed_count: int):
        """Print summary of the states process."""
        try:
            with self.db:
                # Get statistics
                stats = self.db.get_state_processing_stats()

                self.logger.info("=" * 50)
                self.logger.info("STATES PROCESS SUMMARY")
                self.logger.info("=" * 50)
                self.logger.info(f"Records processed: {processed_count:,}")
                self.logger.info(f"Records with matching states: {stats.get('same_state_count', 0):,}")
                self.logger.info(f"Records with different states: {stats.get('different_state_count', 0):,}")
                self.logger.info(f"Records with missing state data: {stats.get('missing_state_count', 0):,}")
                self.logger.info("\nNext steps:")
                self.logger.info("- Run 'python main.py url_check' to perform URL matching")
                self.logger.info("- Run 'python main.py content_hash' to generate content hashes")
                self.logger.info("- Run 'python main.py embedding' to perform semantic analysis")
                self.logger.info("=" * 50)
        except Exception as e:
            self.logger.error(f"Could not generate detailed summary: {e}")
            self.logger.info("=" * 50)