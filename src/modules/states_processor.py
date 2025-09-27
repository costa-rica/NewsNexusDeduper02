"""
States processor for NewsNexusDeduper02.
Handles steps 3-5: Populate state information and state matching flags.
"""

from typing import List, Dict, Any
from tqdm import tqdm

from .database import DatabaseConnection


class StatesProcessor:
    """Processes the states command: populate state information and matching flags."""

    def __init__(self):
        """Initialize the states processor."""
        self.db = DatabaseConnection()

    def execute(self):
        """
        Execute the states process:
        3. Populate articleNewState using relationship between Article, ArticleStateContract, and State
        4. Populate articleApprovedState using the same relationship
        5. Populate sameStateFlag (1 if states match, 0 otherwise)
        """
        print("Starting states process...")

        try:
            with self.db:
                # Get all analysis records that need state information
                print("Getting analysis records to update...")
                analysis_records = self.db.get_analysis_records_for_state_update()

                if not analysis_records:
                    print("No analysis records found to update")
                    return

                print(f"Found {len(analysis_records):,} analysis records to update")

                # Process records in batches
                batch_size = 1000
                batch_updates = []
                processed_count = 0

                print("Processing state information...")
                with tqdm(total=len(analysis_records), desc="Processing states", unit="records") as pbar:
                    for record in analysis_records:
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
                            pbar.update(len(batch_updates))
                            batch_updates = []

                    # Process remaining updates
                    if batch_updates:
                        self._update_batch(batch_updates)
                        pbar.update(len(batch_updates))

                print(f"Successfully processed {processed_count:,} records")
                self._print_summary(processed_count)

        except Exception as e:
            print(f"Error during states processing: {e}")
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

                print("\n" + "="*50)
                print("STATES PROCESS SUMMARY")
                print("="*50)
                print(f"Records processed: {processed_count:,}")
                print(f"Records with matching states: {stats.get('same_state_count', 0):,}")
                print(f"Records with different states: {stats.get('different_state_count', 0):,}")
                print(f"Records with missing state data: {stats.get('missing_state_count', 0):,}")
                print("\nNext steps:")
                print("- Run 'python main.py url_check' to perform URL matching")
                print("- Run 'python main.py content_hash' to generate content hashes")
                print("- Run 'python main.py embedding' to perform semantic analysis")
                print("="*50)
        except Exception as e:
            print(f"Could not generate detailed summary: {e}")
            print("="*50)