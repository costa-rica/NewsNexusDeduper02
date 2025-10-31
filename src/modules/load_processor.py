"""
Load processor for NewsNexusDeduper02.
Handles steps 1-2: Populate article combinations and same ID flags.
"""

import os
from typing import List, Dict, Any

from .database import DatabaseConnection
from .csv_reader import CSVReader
from .logger import get_logger


class LoadProcessor:
    """Processes the load command: populate combinations and same ID flags."""

    def __init__(self, report_id: int = None):
        """Initialize the load processor.

        Args:
            report_id: Optional report ID to load articles from ArticleReportContracts instead of CSV
        """
        self.db = DatabaseConnection()
        self.report_id = report_id
        self.logger = get_logger(__name__)
        self.use_tqdm = os.getenv("RUN_ENVIRONMENT", "production").lower() == "workstation"

    def execute(self):
        """
        Execute the load process:
        1. Read article IDs from CSV or database (based on report_id)
        2. Get all approved article IDs
        3. Create all combinations (new article x approved article)
        4. Populate sameArticleIdFlag
        5. Insert into ArticleDuplicateAnalysis table
        """
        self.logger.info("Starting load process...")

        # Step 1: Get article IDs from either database (by reportId) or CSV
        if self.report_id is not None:
            self.logger.info(f"Loading article IDs from database for reportId {self.report_id}...")
            try:
                with self.db:
                    new_article_ids = self.db.get_article_ids_by_report_id(self.report_id)
                    self.logger.info(f"Found {len(new_article_ids)} article IDs for report {self.report_id}")
            except Exception as e:
                self.logger.error(f"Error reading article IDs from database: {e}")
                return
        else:
            self.logger.info("Reading article IDs from CSV...")
            try:
                csv_reader = CSVReader()
                new_article_ids = csv_reader.read_article_ids()
                self.logger.info(f"Found {len(new_article_ids)} article IDs in CSV")
            except Exception as e:
                self.logger.error(f"Error reading CSV: {e}")
                return

        if not new_article_ids:
            source = f"report {self.report_id}" if self.report_id else "CSV file"
            self.logger.warning(f"No article IDs found in {source}")
            return

        # Step 2: Get all approved article IDs
        self.logger.info("Getting approved article IDs from database...")
        try:
            with self.db:
                approved_article_ids = self.db.get_all_approved_article_ids()
                self.logger.info(f"Found {len(approved_article_ids)} approved articles")
        except Exception as e:
            self.logger.error(f"Error getting approved articles: {e}")
            return

        if not approved_article_ids:
            self.logger.warning("No approved articles found in database")
            return

        # Calculate total combinations
        total_combinations = len(new_article_ids) * len(approved_article_ids)
        self.logger.info(f"Will create {total_combinations:,} comparison records")

        # Step 3: Clear existing analysis for these articles
        self.logger.info("Clearing existing analysis data...")
        try:
            with self.db:
                self.db.clear_existing_analysis_for_articles(new_article_ids)
        except Exception as e:
            self.logger.error(f"Error clearing existing data: {e}")
            return

        # Step 4: Generate combinations and insert in batches
        self.logger.info("Generating combinations and populating database...")
        batch_size = 1000  # Process in batches to avoid memory issues
        batch_data = []
        processed_count = 0
        next_log_threshold = 0.1  # 10%

        try:
            with self.db:
                # Setup progress tracking based on environment
                if self.use_tqdm:
                    from tqdm import tqdm
                    pbar = tqdm(total=total_combinations, desc="Processing combinations", unit="records")

                for new_article_id in new_article_ids:
                    for approved_article_id in approved_article_ids:
                        # Create analysis record
                        analysis_record = {
                            'articleIdNew': new_article_id,
                            'articleIdApproved': approved_article_id,
                            'reportId': self.report_id,  # Optional field - None if not provided
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
                            if self.use_tqdm:
                                pbar.update(len(batch_data))
                            batch_data = []

                        # Log progress for server environment
                        if not self.use_tqdm and total_combinations > 0:
                            ratio = processed_count / total_combinations
                            if ratio >= next_log_threshold or processed_count == total_combinations:
                                percent = int(ratio * 100)
                                self.logger.info(f"Processing combinations: {percent}% ({processed_count:,}/{total_combinations:,})")
                                next_log_threshold += 0.1

                # Insert remaining records
                if batch_data:
                    self._insert_batch(batch_data)
                    if self.use_tqdm:
                        pbar.update(len(batch_data))

                if self.use_tqdm:
                    pbar.close()

                self.logger.info(f"Successfully processed {processed_count:,} combinations")
                self._print_summary(new_article_ids, approved_article_ids, processed_count)

        except Exception as e:
            self.logger.error(f"Error during processing: {e}")
            return

    def _insert_batch(self, batch_data: List[Dict[str, Any]]):
        """Insert a batch of analysis records."""
        if batch_data:
            self.db.insert_article_duplicate_analysis_batch(batch_data)

    def _print_summary(self, new_article_ids: List[int], approved_article_ids: List[int], processed_count: int):
        """Print summary of the load process."""
        same_id_count = len([aid for aid in new_article_ids if aid in approved_article_ids])

        self.logger.info("=" * 50)
        self.logger.info("LOAD PROCESS SUMMARY")
        self.logger.info("=" * 50)
        self.logger.info(f"New articles from CSV: {len(new_article_ids)}")
        self.logger.info(f"Approved articles in DB: {len(approved_article_ids)}")
        self.logger.info(f"Total combinations created: {processed_count:,}")
        self.logger.info(f"Records with sameArticleIdFlag=1: {same_id_count}")
        self.logger.info(f"Records with sameArticleIdFlag=0: {processed_count - same_id_count:,}")
        self.logger.info("\nNext steps:")
        self.logger.info("- Run 'python main.py states' to populate state information")
        self.logger.info("- Run 'python main.py url_check' to perform URL matching")
        self.logger.info("- Run 'python main.py content_hash' to generate content hashes")
        self.logger.info("- Run 'python main.py embedding' to perform semantic analysis")
        self.logger.info("=" * 50)