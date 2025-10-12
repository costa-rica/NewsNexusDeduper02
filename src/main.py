#!/usr/bin/env python3
"""
NewsNexusDeduper02 - Main entry point for article deduplication operations.

Commands:
- load: Populate article combinations and same ID flags (steps 1-2)
- states: Populate state information and state matching flags (steps 3-5)
- url_check: Perform URL canonicalization and matching (step 6)
- content_hash: Generate content hashes for similarity detection (step 7)
- embedding: Perform semantic similarity analysis using embeddings (step 8)
- analyze: Run complete pipeline (load → states → url_check → content_hash → embedding)
- analyze_fast: Run fast pipeline (load → states → url_check → embedding, skips content_hash)
"""

import sys
import argparse
from pathlib import Path

# Add the src directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent))

from modules.load_processor import LoadProcessor
from modules.states_processor import StatesProcessor
from modules.url_check_processor import UrlCheckProcessor
from modules.content_hash_processor import ContentHashProcessor
from modules.embedding_processor import EmbeddingProcessor
from modules.database import DatabaseConnection


def run_analyze(report_id=None):
    """Run complete analysis pipeline: load, states, url_check, content_hash, embedding.

    Args:
        report_id: Optional report ID to pass to LoadProcessor
    """
    pipeline_steps = [
        ("load", "Loading article combinations and same ID flags", LoadProcessor),
        ("states", "Processing state information and matching flags", StatesProcessor),
        ("url_check", "Performing URL canonicalization and matching", UrlCheckProcessor),
        ("content_hash", "Generating content hashes for similarity detection", ContentHashProcessor),
        ("embedding", "Performing semantic similarity analysis", EmbeddingProcessor)
    ]

    print("="*60)
    print("STARTING COMPLETE ANALYSIS PIPELINE")
    print("="*60)
    print("Steps: load → states → url_check → content_hash → embedding")
    if report_id:
        print(f"Report ID: {report_id}")
    print("="*60)

    # Clear existing data before starting
    print("\nClearing ArticleDuplicateAnalyses table...")
    try:
        with DatabaseConnection() as db:
            rows_deleted = db.clear_all_analysis_data()
            print(f"Deleted {rows_deleted:,} existing rows from ArticleDuplicateAnalyses table.")
    except Exception as e:
        print(f"Error clearing table: {e}")
        sys.exit(1)

    for step_name, description, processor_class in pipeline_steps:
        try:
            print(f"\n🔄 Step {pipeline_steps.index((step_name, description, processor_class)) + 1}/5: {description}...")
            # Pass report_id only to LoadProcessor
            if step_name == "load":
                processor = processor_class(report_id=report_id)
            else:
                processor = processor_class()
            processor.execute()
            print(f"✅ Step {step_name} completed successfully")
        except Exception as e:
            print(f"❌ Error in step {step_name}: {e}")
            print("Pipeline stopped due to error.")
            sys.exit(1)

    print("\n" + "="*60)
    print("🎉 COMPLETE ANALYSIS PIPELINE FINISHED SUCCESSFULLY")
    print("="*60)
    print("All steps completed: load, states, url_check, content_hash, embedding")
    print("Your duplicate analysis is ready for review!")
    print("="*60)


def run_analyze_fast(report_id=None):
    """Run fast analysis pipeline: load, states, url_check, embedding (skips content_hash).

    Args:
        report_id: Optional report ID to pass to LoadProcessor
    """
    pipeline_steps = [
        ("load", "Loading article combinations and same ID flags", LoadProcessor),
        ("states", "Processing state information and matching flags", StatesProcessor),
        ("url_check", "Performing URL canonicalization and matching", UrlCheckProcessor),
        ("embedding", "Performing semantic similarity analysis", EmbeddingProcessor)
    ]

    print("="*60)
    print("STARTING FAST ANALYSIS PIPELINE")
    print("="*60)
    print("Steps: load → states → url_check → embedding (skipping content_hash)")
    if report_id:
        print(f"Report ID: {report_id}")
    print("="*60)

    # Clear existing data before starting
    print("\nClearing ArticleDuplicateAnalyses table...")
    try:
        with DatabaseConnection() as db:
            rows_deleted = db.clear_all_analysis_data()
            print(f"Deleted {rows_deleted:,} existing rows from ArticleDuplicateAnalyses table.")
    except Exception as e:
        print(f"Error clearing table: {e}")
        sys.exit(1)

    for step_name, description, processor_class in pipeline_steps:
        try:
            print(f"\n🔄 Step {pipeline_steps.index((step_name, description, processor_class)) + 1}/4: {description}...")
            # Pass report_id only to LoadProcessor
            if step_name == "load":
                processor = processor_class(report_id=report_id)
            else:
                processor = processor_class()
            processor.execute()
            print(f"✅ Step {step_name} completed successfully")
        except Exception as e:
            print(f"❌ Error in step {step_name}: {e}")
            print("Pipeline stopped due to error.")
            sys.exit(1)

    print("\n" + "="*60)
    print("🎉 FAST ANALYSIS PIPELINE FINISHED SUCCESSFULLY")
    print("="*60)
    print("Completed steps: load, states, url_check, embedding")
    print("Note: content_hash was skipped for faster processing")
    print("Run 'python src/main.py content_hash' if you need content similarity analysis")
    print("="*60)


def clear_table(skip_confirmation=False):
    """Clear all rows from the ArticleDuplicateAnalyses table."""
    print("Clearing ArticleDuplicateAnalyses table...")

    # Ask for confirmation unless -y flag is used
    if not skip_confirmation:
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
    load_parser.add_argument('--report-id', type=int, help='Load articles from ArticleReportContracts for this report ID instead of CSV')

    # Clear table command
    clear_parser = subparsers.add_parser('clear_table', help='Delete all rows from ArticleDuplicateAnalyses table')
    clear_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation prompt')

    # States command
    states_parser = subparsers.add_parser('states', help='Populate state information and matching flags')

    # URL check command
    url_parser = subparsers.add_parser('url_check', help='Perform URL canonicalization and matching')

    # Content hash command
    hash_parser = subparsers.add_parser('content_hash', help='Generate content hashes for similarity detection')

    # Embedding command
    embedding_parser = subparsers.add_parser('embedding', help='Perform semantic similarity analysis')

    # Analyze command (full pipeline)
    analyze_parser = subparsers.add_parser('analyze', help='Run complete analysis pipeline (load, states, url_check, content_hash, embedding)')
    analyze_parser.add_argument('--report-id', type=int, help='Load articles from ArticleReportContracts for this report ID instead of CSV')

    # Analyze fast command (skip content_hash)
    analyze_fast_parser = subparsers.add_parser('analyze_fast', help='Run fast analysis pipeline (load, states, url_check, embedding) - skips content_hash')
    analyze_fast_parser.add_argument('--report-id', type=int, help='Load articles from ArticleReportContracts for this report ID instead of CSV')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == 'load':
            report_id = getattr(args, 'report_id', None)
            processor = LoadProcessor(report_id=report_id)
            processor.execute()
        elif args.command == 'clear_table':
            clear_table(skip_confirmation=args.yes)
        elif args.command == 'states':
            processor = StatesProcessor()
            processor.execute()
        elif args.command == 'url_check':
            processor = UrlCheckProcessor()
            processor.execute()
        elif args.command == 'content_hash':
            processor = ContentHashProcessor()
            processor.execute()
        elif args.command == 'embedding':
            processor = EmbeddingProcessor()
            processor.execute()
        elif args.command == 'analyze':
            report_id = getattr(args, 'report_id', None)
            run_analyze(report_id=report_id)
        elif args.command == 'analyze_fast':
            report_id = getattr(args, 'report_id', None)
            run_analyze_fast(report_id=report_id)
        else:
            print(f"Unknown command: {args.command}")
            sys.exit(1)

    except Exception as e:
        print(f"Error executing {args.command}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()