"""
CSV file reading utilities for NewsNexusDeduper02.
"""

import csv
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv


class CSVReader:
    """Handles reading article IDs from CSV files."""

    def __init__(self):
        """Initialize CSV reader using environment variables."""
        load_dotenv()

        self.csv_path = os.getenv('PATH_TO_CSV')
        if not self.csv_path:
            raise ValueError("PATH_TO_CSV must be set in .env file")

        self.csv_file = Path(self.csv_path)
        if not self.csv_file.exists():
            raise FileNotFoundError(f"CSV file not found at {self.csv_path}")

    def read_article_ids(self) -> List[int]:
        """
        Read article IDs from CSV file.

        Assumes the CSV has a column containing article IDs.
        Returns a list of unique integer article IDs.
        """
        article_ids = []

        with open(self.csv_file, 'r', encoding='utf-8') as file:
            # Detect if file has headers
            sample = file.read(1024)
            file.seek(0)

            # Try to detect delimiter with fallback options
            delimiter = ','  # Default fallback
            try:
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample, delimiters=',;\t|').delimiter
            except csv.Error:
                # If sniffer fails, try common delimiters
                for test_delimiter in [',', ';', '\t', '|']:
                    if test_delimiter in sample:
                        delimiter = test_delimiter
                        break

            reader = csv.reader(file, delimiter=delimiter)

            # Check if first row contains headers (non-numeric first column)
            first_row = next(reader)
            file.seek(0)

            has_header = False
            try:
                # If first cell can't be converted to int, assume it's a header
                int(first_row[0].strip())
            except (ValueError, IndexError):
                has_header = True

            # Re-read with proper header setting
            reader = csv.DictReader(file, delimiter=delimiter) if has_header else csv.reader(file, delimiter=delimiter)

            if has_header:
                # Try to find article ID column by name
                fieldnames = reader.fieldnames or []
                id_column = None

                # Look for common article ID column names
                possible_names = ['articleId', 'article_id', 'id', 'ArticleId', 'ID']
                for name in possible_names:
                    if name in fieldnames:
                        id_column = name
                        break

                if not id_column and fieldnames:
                    # If no match, use first column
                    id_column = fieldnames[0]

                if id_column:
                    for row in reader:
                        try:
                            article_id = int(str(row[id_column]).strip())
                            article_ids.append(article_id)
                        except (ValueError, KeyError):
                            continue
                else:
                    raise ValueError("Could not determine article ID column in CSV")
            else:
                # No headers, assume first column contains article IDs
                file.seek(0)
                reader = csv.reader(file, delimiter=delimiter)
                for row in reader:
                    if row:  # Skip empty rows
                        try:
                            article_id = int(row[0].strip())
                            article_ids.append(article_id)
                        except (ValueError, IndexError):
                            continue

        # Return unique article IDs, preserving order
        unique_ids = []
        seen = set()
        for article_id in article_ids:
            if article_id not in seen:
                unique_ids.append(article_id)
                seen.add(article_id)

        return unique_ids

    def get_csv_info(self) -> dict:
        """Get information about the CSV file."""
        return {
            'path': str(self.csv_file),
            'exists': self.csv_file.exists(),
            'size_bytes': self.csv_file.stat().st_size if self.csv_file.exists() else 0
        }