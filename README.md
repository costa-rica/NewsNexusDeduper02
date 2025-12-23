# NewsNexus Deduper

## Overview

This Python micro service assists in the effort to identify duplicate approved articles in the News Nexus 09 database. The service will use articleIds from a csv file to analyze with approved articles in the database's ArticleApproved table. The service will look at data in the Articles, ArticlesApproveds, ArticleStateContracts tables.

## How to run

1. **Activate virtual environment:**

   ```bash
   source /Users/nick/Documents/_environments/deduper/bin/activate
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run commands:**

```bash
# Individual processing steps
python src/main.py load                    # Create article comparison pairs from CSV
python src/main.py load --report-id 138    # Or load articles from a specific report
python src/main.py states                  # Populate state associations and state match flags
python src/main.py url_check               # Perform URL canonicalization and matching
python src/main.py content_hash            # Generate content hashes for similarity detection
python src/main.py embedding               # Calculate semantic similarity using embeddings

# Pipeline commands (run all steps in sequence)
python src/main.py analyze                 # Complete pipeline from CSV
python src/main.py analyze --report-id 138 # Complete pipeline from report
python src/main.py analyze_fast            # Fast pipeline (skips content_hash) from CSV
python src/main.py analyze_fast --report-id 138  # Fast pipeline from report

# Utility commands
python src/main.py clear_table             # Clear all records (with confirmation)
python src/main.py clear_table -y          # Clear all records (skip confirmation)
python src/main.py --help                  # Show all available commands and options
```

## .env
```
NAME_APP=nn-deduper
RUN_ENVIRONMENT=server
PATH_TO_DATABASE=/Users/nick/Documents/_databases/NewsNexus09
NAME_DB=newsnexus09.db
PATH_TO_PYTHON_VENV=/Users/nick/Documents/_environments/news_nexus
PATH_TO_MICROSERVICE_DEDUPER=/Users/nick/Documents/NewsNexusDeduper02
PATH_TO_MICROSERVICE_LOCATION_SCORER=/Users/nick/Documents/NewsNexusClassifierLocationScorer01
```

- optional if not using --report-id
```
PATH_TO_CSV=/Users/nick/Documents/_project_resources/NewsNexus09/utilities/deduper/article_ids.csv
```

## References

- [Overview of News Nexus 09](docs/NEWS_NEXUS_09.md)
- [Database schema and relationships](docs/DATABASE_OVERVIEW.md)

## How It Works

NewsNexusDeduper02 identifies duplicate articles by comparing newly ingested articles against approximately 3,000 approved articles in the News Nexus 09 database. The system uses multiple similarity detection methods to create comprehensive duplicate analysis records.

### Processing Pipeline

The deduplication analysis follows an 8-step workflow that populates the `ArticleDuplicateAnalyses` table:

1. **Article Combination Setup** - Creates comparison pairs between new articles (from CSV input or report) and all approved articles
2. **ID Matching** - Flags exact ID matches between new and approved articles
3. **State Association** - Maps articles to their geographic states using the ArticleStateContract junction table
4. **State Comparison** - Compares state associations between article pairs
5. **State Matching Flags** - Sets binary flags for state matches
6. **URL Canonicalization** - Normalizes and compares article URLs for exact matches
7. **Content Hashing** - Generates SimHash/MinHash fingerprints and SHA-1 hashes for content similarity
8. **Semantic Analysis** - Calculates cosine similarity using all-MiniLM-L6-v2 embeddings for semantic duplicate detection

### Database Schema

The analysis results are stored in the `ArticleDuplicateAnalyses` table:

```
| Field                | Type    | Description                                          |
| -------------------- | ------- | ---------------------------------------------------- |
| id                   | INTEGER | Unique analysis identifier                           |
| articleIdNew         | INTEGER | ID of the newly ingested article                     |
| articleIdApproved    | INTEGER | ID of the previously approved article                |
| reportId             | INTEGER | Optional report ID (when using --report-id)          |
| sameArticleIdFlag    | INTEGER | 1 if IDs match; 0 otherwise                          |
| articleNewState      | STRING  | State associated with the new article                |
| articleApprovedState | STRING  | State associated with the approved article           |
| sameStateFlag        | INTEGER | 1 if states match; 0 otherwise                       |
| urlCheck             | INTEGER | URL match result (1 for match, 0 for no match)       |
| contentHash          | FLOAT   | Content similarity score from hash comparison        |
| embeddingSearch      | FLOAT   | Semantic similarity score from embedding analysis    |
| createdAt            | DATE    | Record creation timestamp                            |
| updatedAt            | DATE    | Record update timestamp                              |
```

### Data Sources

- **Articles Table**: Provides URLs and article indexing
- **ArticleApproved Table**: Provides content, titles, dates, and text for comparison analysis
- **ArticleStateContract + States Tables**: Provides geographic state associations
- **Input CSV or ArticleReportContracts Table**: Contains article IDs of newly ingested articles to analyze

### Analysis Scale

For each new article in the input CSV, the system creates comparison records against all ~3,000 approved articles. For example, 10 new articles generate 30,000 analysis records, with each record containing multiple similarity metrics for comprehensive duplicate detection.

⸻
