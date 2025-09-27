# NewsNexus Deduper

## Overview

This Python micro service assists in the effort to identify duplicate approved articles in the News Nexus 09 database. The service will use articleIds from a csv file to analyze with approved articles in the database's ArticleApproved table. The service will look at data in the Articles, ArticlesApproveds, ArticleStateContracts tables.

## .env

```
PATH_TO_DATABASE=/Users/nick/Documents/_databases/NewsNexus09
NAME_DB=newsnexus09.db
PATH_TO_PYTHON_VENV=/Users/nick/Documents/_environments/deduper
PATH_TO_CSV=/Users/nick/Documents/_project_resources/NewsNexus09/utilities/deduper/article_ids.csv
```

## References

- [Overview of News Nexus 09](docs/NEWS_NEXUS_09.md)
- [Database schema and relationships](docs/DATABASE_OVERVIEW.md)

## Prompt for Claude

I would like us to build a micro service called the NewsNexusDeduper02. It will be a Python project. The goal of this project is to determine if a new article that has been approved is a duplicate of an existing article. A duplicate consists of either the article being exactly the same or if the event taken place in the article is the same as another article.

The News Nexus 09 database has an ArticleApproveds table which is currently at around 3,000 articles. I would like this version of the NewsNexusDeduper, let’s call it NewsNexusDeduper02 to use a csv file of articleIds, which correspond to the ids of rows in the Articles table will then be used to compare each article in the ArticleApproveds table.

The important caveat to note while the Articles table will be the index that is used to keep track of articles. The content in the ArticleApproveds table will be what is used to compare between the articles for duplicates. Except the urls, that will come from the Articles table, but the dates, title, state, and content will all come from the ArticleApproveds table.

The NewsNexusDeduper will populate the ArticleDuplicateAnalysis table

```
| Field                | Type    | Constraints                 | Description                                          |
| -------------------- | ------- | --------------------------- | ---------------------------------------------------- |
| id                   | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Unique analysis identifier                           |
| articleIdNew         | INTEGER | FK, NOT NULL                | ID of the newly ingested article                     |
| articleIdApproved    | INTEGER | FK, NOT NULL                | ID of the previously approved article                |
| sameArticleIdFlag    | INTEGER | NOT NULL                    | 1 if IDs match; 0 otherwise                          |
| articleNewState      | STRING  | NOT NULL                    | State associated with the new article                |
| articleApprovedState | STRING  | NOT NULL                    | State associated with the approved article           |
| sameStateFlag        | INTEGER | NOT NULL                    | 1 if states match; 0 otherwise                       |
| urlCheck             | INTEGER | NOT NULL                    | URL match check result (e.g., 1 match / 0 no match)  |
| contentHash          | INTEGER | NOT NULL                    | Hash comparison result indicator for article content |
| embeddingSearch      | INTEGER | NOT NULL                    | Embedding similarity result indicator                |
| createdAt            | DATE    | NOT NULL                    | Timestamp                                            |
| updatedAt            | DATE    | NOT NULL                    | Timestamp                                            |
```

The first set of columns will be the indexing columns:
id: unique id for the AritlceDuplicate table
articleIdNew: articleId from the Articles table of the new article
articleIdApproved: articleId from the Articles table of the already approved article.

The first step for NewsNexusDeduper02 is to populate these columns using the .csv file with new approved articles and the column articleIdApproved. So for example, if there are 100 new articles and 3000 articles in the articleIdApproved table we will have 300,000 rows in the ArticleDuplicateRatings. Where each new article is matched up with an existing approved article. Since the new articles will also be in the ArticlesApproveds table we’ll have some rows where the articleIdNew and the articleIdApproved columns match.

Let’s call this module or a python file. I would like this micro service to be modular and consistent with best practices. So we can isolate issues when debugging.

For the project structure, I want to use an src/ directory to store code. I want the entry point to be src/main.py and the environment will be stored outside of the project folder.

### Workflow steps

1. populate combinations of articleIdNew and articleIdApproved column.
2. Populate sameArticleIdFlag, 1 if articleIdNew = articleIdApproved, 0 otherwise
3. populate articleNewState. This column will use relationship between the Article (id), ArticleStateContract (articleId), and State to populate the abbreviation
4. populate articleApprovedState, similar to articleNewState use the relationship between the Article (id), ArticleStateContract (articleId), and State to populate the abbreviation
5. sameStateFlag, 1 if articleNewState = articleApprovedState, 0 otherwise
6. populate urlCheck (e.g., 1 for match / 0 for no match, or a confidence 0–1).URL Canonicalization + Exact URL Match (fast)
7. Populates contentHash. similarity 0–1; or 1/0 for exact . Tooling: SimHash or MinHash (Python), plus SHA-1 for exact.
8. Populate embeddingSearch (cosine similarity 0–1): Embedding Search (semantic similarity) Tooling: all-MiniLM-L6-v2 embeddings (Node via @xenova/transformers or Python via sentence-transformers) + FAISS (or a simple cosine if corpus is small).

As I mentioned make this project modular. But I would also like one terminal command for groups of these steps. Commands:
`python main.py load`: executes steps 1 and 2
`python main.py states`: executes steps 3, 4, and 5,
`python main.py url_check`:executes step 6
`python main.py content_hash`: executes step 7
`python main.py embedding`: executes step 8

For each command use terminal progress bar using the tqdm.

The database is stored in the .env

```
PATH_TO_DATABASE=/Users/nick/Documents/_databases/NewsNexus09
NAME_DB=newsnexus09.db
PATH_TO_PYTHON_VENV=/Users/nick/Documents/_environments/deduper
PATH_TO_CSV=/Users/nick/Documents/_project_resources/NewsNexus09/utilities/deduper/article_ids.csv
```
