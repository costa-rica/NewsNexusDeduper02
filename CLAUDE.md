# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NewsNexusDeduper02 is a Python microservice that identifies duplicate articles in the News Nexus 09 database. It compares newly ingested articles against ~3,000 approved articles using multiple similarity detection methods.

## Commands

### Main Operations

- `python src/main.py load` - Populate article combinations and same ID flags (steps 1-2)
- `python src/main.py states` - Populate state information and state matching flags (steps 3-5)
- `python src/main.py url_check` - Perform URL canonicalization and matching (step 6)
- `python src/main.py content_hash` - Generate content hashes for similarity detection (step 7)
- `python src/main.py embedding` - Perform semantic similarity analysis using embeddings (step 8)

### Environment Setup

The project uses a Python virtual environment located outside the project directory:

- Virtual environment path: `PATH_TO_PYTHON_VENV` (from .env)
- Activate with: `source {PATH_TO_PYTHON_VENV}/bin/activate`

## Architecture

### Database Integration

- **Database**: NewsNexusDb09 (SQLite with Sequelize ORM)
- **Target Table**: `ArticleDuplicateAnalysis` - stores all comparison results
- **Source Tables**:
  - `Articles` - provides URLs and base article data
  - `ArticleApproved` - provides content, titles, dates for comparison
  - `ArticleStateContract` + `States` - provides state associations

### Data Flow

1. Input CSV file contains article IDs for new articles to process
2. Each new article is compared against all approved articles (~3,000), creating [COUNT_OF_NEW_ARTICLES * 3000] comparisons
3. Multiple similarity metrics are calculated and stored:
   - ID matching (exact duplicates)
   - State matching (geographic relevance)
   - URL canonicalization and matching
   - Content hashing (SimHash/MinHash + SHA-1)
   - Semantic embedding similarity (all-MiniLM-L6-v2 + cosine similarity)

### Project Structure

```
NewsNexusDeduper02/
├── src/              # Main source directory
│   └── main.py       # Entry point with command handling
├── docs/             # Documentation
│   ├── DATABASE_OVERVIEW.md
│   └── NEWS_NEXUS_09.md
├── .env              # Environment configuration
└── README.md         # Project documentation
```

### Key Environment Variables

- `PATH_TO_DATABASE` - Directory containing the NewsNexus09 database
- `NAME_DB` - Database filename (newsnexus09.db)
- `PATH_TO_CSV` - Input CSV file with article IDs to process
- `PATH_TO_PYTHON_VENV` - Virtual environment path

## Development Notes

### Database Schema Context

- All tables use `createdAt`/`updatedAt` timestamps
- Foreign keys reference `Articles.id` for article relationships
- State associations use junction table `ArticleStateContract`
- Content comparison uses `ArticleApproved` table data, not raw `Articles` content

### Progress Tracking

All operations use tqdm for terminal progress bars to track processing of large datasets.

### Similarity Detection Methods

1. **URL Check**: Canonicalization + exact matching
2. **Content Hash**: SimHash/MinHash for near-duplicate detection, SHA-1 for exact matches
3. **Embedding Search**: Semantic similarity using sentence-transformers with cosine similarity
