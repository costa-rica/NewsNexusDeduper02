"""
Load processor for NewsNexusDeduper02.
Handles steps 1-2: Populate article combinations and same ID flags.
"""

from typing import List, Dict, Any
from tqdm import tqdm

from .database import DatabaseConnection
from .csv_reader import CSVReader


class LoadProcessor:
    """Processes the load command: populate combinations and same ID flags."""

    def __init__(self):
        """Initialize the load processor."""
        self.db = DatabaseConnection()
        self.csv_reader = CSVReader()

    def execute(self):
        """
        Execute the load process:
        1. Read article IDs from CSV
        2. Get all approved article IDs
        3. Create all combinations (new article x approved article)
        4. Populate sameArticleIdFlag
        5. Insert into ArticleDuplicateAnalysis table
        """
        print("Starting load process...")

        # Step 1: Read article IDs from CSV
        print("Reading article IDs from CSV...")
        try:
            new_article_ids = self.csv_reader.read_article_ids()
            print(f"Found {len(new_article_ids)} article IDs in CSV")
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return

        if not new_article_ids:
            print("No article IDs found in CSV file")
            return

        # Step 2: Get all approved article IDs
        print("Getting approved article IDs from database...")
        try:
            with self.db:
                approved_article_ids = self.db.get_all_approved_article_ids()
                print(f"Found {len(approved_article_ids)} approved articles")
        except Exception as e:
            print(f"Error getting approved articles: {e}")
            return

        if not approved_article_ids:
            print("No approved articles found in database")
            return

        # Calculate total combinations
        total_combinations = len(new_article_ids) * len(approved_article_ids)
        print(f"Will create {total_combinations:,} comparison records")

        # Step 3: Clear existing analysis for these articles
        print("Clearing existing analysis data...")
        try:
            with self.db:
                self.db.clear_existing_analysis_for_articles(new_article_ids)
        except Exception as e:
            print(f"Error clearing existing data: {e}")
            return

        # Step 4: Generate combinations and insert in batches
        print("Generating combinations and populating database...")
        batch_size = 1000  # Process in batches to avoid memory issues
        batch_data = []
        processed_count = 0

        try:
            with self.db:
                # Create progress bar
                with tqdm(total=total_combinations, desc="Processing combinations", unit="records") as pbar:
                    for new_article_id in new_article_ids:
                        for approved_article_id in approved_article_ids:
                            # Create analysis record
                            analysis_record = {
                                'articleIdNew': new_article_id,
                                'articleIdApproved': approved_article_id,
                                'sameArticleIdFlag': 1 if new_article_id == approved_article_id else 0,
                                'articleNewState': '',  # Will be populated in states step
                                'articleApprovedState': '',  # Will be populated in states step
                                'sameStateFlag': 0,  # Will be populated in states step
                                'urlCheck': 0,  # Will be populated in url_check step
                                'contentHash': 0,  # Will be populated in content_hash step
                                'embeddingSearch': 0  # Will be populated in embedding step
                            }

                            batch_data.append(analysis_record)
                            processed_count += 1

                            # Insert batch when it reaches batch_size
                            if len(batch_data) >= batch_size:
                                self._insert_batch(batch_data)
                                pbar.update(len(batch_data))
                                batch_data = []

                    # Insert remaining records
                    if batch_data:
                        self._insert_batch(batch_data)
                        pbar.update(len(batch_data))

                print(f"Successfully processed {processed_count:,} combinations")
                self._print_summary(new_article_ids, approved_article_ids, processed_count)

        except Exception as e:
            print(f"Error during processing: {e}")
            return

    def _insert_batch(self, batch_data: List[Dict[str, Any]]):
        """Insert a batch of analysis records."""
        if batch_data:
            self.db.insert_article_duplicate_analysis_batch(batch_data)

    def _print_summary(self, new_article_ids: List[int], approved_article_ids: List[int], processed_count: int):
        """Print summary of the load process."""
        same_id_count = len([aid for aid in new_article_ids if aid in approved_article_ids])

        print("\n" + "="*50)
        print("LOAD PROCESS SUMMARY")
        print("="*50)
        print(f"New articles from CSV: {len(new_article_ids)}")
        print(f"Approved articles in DB: {len(approved_article_ids)}")
        print(f"Total combinations created: {processed_count:,}")
        print(f"Records with sameArticleIdFlag=1: {same_id_count}")
        print(f"Records with sameArticleIdFlag=0: {processed_count - same_id_count:,}")
        print("\nNext steps:")
        print("- Run 'python main.py states' to populate state information")
        print("- Run 'python main.py url_check' to perform URL matching")
        print("- Run 'python main.py content_hash' to generate content hashes")
        print("- Run 'python main.py embedding' to perform semantic analysis")
        print("="*50)