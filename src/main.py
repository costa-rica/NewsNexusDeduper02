#!/usr/bin/env python3
"""
NewsNexusDeduper02 - Main entry point for article deduplication operations.

Commands:
- load: Populate article combinations and same ID flags (steps 1-2)
- states: Populate state information and state matching flags (steps 3-5)
- url_check: Perform URL canonicalization and matching (step 6)
- content_hash: Generate content hashes for similarity detection (step 7)
- embedding: Perform semantic similarity analysis using embeddings (step 8)
"""

import sys
import argparse
from pathlib import Path

# Add the src directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent))

from modules.load_processor import LoadProcessor
from modules.states_processor import StatesProcessor
from modules.url_check_processor import UrlCheckProcessor
from modules.database import DatabaseConnection


def clear_table():
    """Clear all rows from the ArticleDuplicateAnalyses table."""
    print("Clearing ArticleDuplicateAnalyses table...")

    # Ask for confirmation
    response = input("This will delete ALL rows from ArticleDuplicateAnalyses table. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        return

    try:
        with DatabaseConnection() as db:
            rows_deleted = db.clear_all_analysis_data()
            print(f"Successfully deleted {rows_deleted:,} rows from ArticleDuplicateAnalyses table.")
    except Exception as e:
        print(f"Error clearing table: {e}")
        sys.exit(1)


def main():
    """Main entry point with command line argument handling."""
    parser = argparse.ArgumentParser(
        description="NewsNexusDeduper02 - Article deduplication microservice"
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Load command
    load_parser = subparsers.add_parser('load', help='Populate article combinations and same ID flags')

    # Clear table command
    clear_parser = subparsers.add_parser('clear_table', help='Delete all rows from ArticleDuplicateAnalyses table')

    # States command
    states_parser = subparsers.add_parser('states', help='Populate state information and matching flags')

    # URL check command
    url_parser = subparsers.add_parser('url_check', help='Perform URL canonicalization and matching')

    # Content hash command
    hash_parser = subparsers.add_parser('content_hash', help='Generate content hashes for similarity detection')

    # Embedding command
    embedding_parser = subparsers.add_parser('embedding', help='Perform semantic similarity analysis')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == 'load':
            processor = LoadProcessor()
            processor.execute()
        elif args.command == 'clear_table':
            clear_table()
        elif args.command == 'states':
            processor = StatesProcessor()
            processor.execute()
        elif args.command == 'url_check':
            processor = UrlCheckProcessor()
            processor.execute()
        elif args.command == 'content_hash':
            print("Content hash command not yet implemented")
            sys.exit(1)
        elif args.command == 'embedding':
            print("Embedding command not yet implemented")
            sys.exit(1)
        else:
            print(f"Unknown command: {args.command}")
            sys.exit(1)

    except Exception as e:
        print(f"Error executing {args.command}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()