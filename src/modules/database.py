"""
Database connection and query utilities for NewsNexusDeduper02.
"""

import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv


class DatabaseConnection:
    """Manages SQLite database connections and operations."""

    def __init__(self):
        """Initialize database connection using environment variables."""
        load_dotenv()

        self.db_path = os.getenv('PATH_TO_DATABASE')
        self.db_name = os.getenv('NAME_DB')

        if not self.db_path or not self.db_name:
            raise ValueError("PATH_TO_DATABASE and NAME_DB must be set in .env file")

        self.full_db_path = Path(self.db_path) / self.db_name

        if not self.full_db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.full_db_path}")

        self._connection = None

    def get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.full_db_path))
            self._connection.row_factory = sqlite3.Row  # Enable dict-like access
        return self._connection

    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results as list of dictionaries."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT query and return the last row ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid

    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute multiple INSERT queries and return number of affected rows."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()
        return cursor.rowcount

    def get_article_ids_from_csv_list(self, article_ids: List[int]) -> List[Dict[str, Any]]:
        """Get article records for given list of IDs."""
        if not article_ids:
            return []

        placeholders = ','.join(['?'] * len(article_ids))
        query = f"""
        SELECT id, url, title, description, publishedDate
        FROM Articles
        WHERE id IN ({placeholders})
        """
        return self.execute_query(query, tuple(article_ids))

    def get_all_approved_article_ids(self) -> List[int]:
        """Get all article IDs from ArticleApproved table."""
        query = """
        SELECT DISTINCT articleId
        FROM ArticleApproveds
        WHERE isApproved = 1
        """
        rows = self.execute_query(query)
        return [row['articleId'] for row in rows]

    def insert_article_duplicate_analysis_batch(self, analysis_data: List[Dict[str, Any]]) -> int:
        """Insert multiple rows into ArticleDuplicateAnalyses table."""
        if not analysis_data:
            return 0

        query = """
        INSERT INTO ArticleDuplicateAnalyses (
            articleIdNew, articleIdApproved, sameArticleIdFlag,
            articleNewState, articleApprovedState, sameStateFlag,
            urlCheck, contentHash, embeddingSearch,
            createdAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """

        params_list = [
            (
                row['articleIdNew'],
                row['articleIdApproved'],
                row['sameArticleIdFlag'],
                row.get('articleNewState', ''),
                row.get('articleApprovedState', ''),
                row.get('sameStateFlag', 0),
                row.get('urlCheck', 0),
                row.get('contentHash', 0),
                row.get('embeddingSearch', 0)
            )
            for row in analysis_data
        ]

        return self.execute_many(query, params_list)

    def clear_existing_analysis_for_articles(self, article_ids: List[int]):
        """Clear existing analysis data for given article IDs."""
        if not article_ids:
            return

        placeholders = ','.join(['?'] * len(article_ids))
        query = f"""
        DELETE FROM ArticleDuplicateAnalyses
        WHERE articleIdNew IN ({placeholders})
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, tuple(article_ids))
        conn.commit()

    def clear_all_analysis_data(self) -> int:
        """Clear all rows from ArticleDuplicateAnalyses table. Returns number of deleted rows."""
        # First count existing rows
        count_query = "SELECT COUNT(*) FROM ArticleDuplicateAnalyses"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(count_query)
        row_count = cursor.fetchone()[0]

        # Delete all rows
        delete_query = "DELETE FROM ArticleDuplicateAnalyses"
        cursor.execute(delete_query)
        conn.commit()

        return row_count

    def get_analysis_records_for_state_update(self) -> List[Dict[str, Any]]:
        """Get analysis records that need state information updated."""
        query = """
        SELECT id, articleIdNew, articleIdApproved
        FROM ArticleDuplicateAnalyses
        WHERE articleNewState = '' OR articleApprovedState = '' OR sameStateFlag = 0
        """
        return self.execute_query(query)

    def get_article_state(self, article_id: int) -> Optional[str]:
        """Get state abbreviation for an article via ArticleStateContract."""
        query = """
        SELECT s.abbreviation
        FROM Articles a
        JOIN ArticleStateContracts asc ON a.id = asc.articleId
        JOIN States s ON asc.stateId = s.id
        WHERE a.id = ?
        LIMIT 1
        """
        rows = self.execute_query(query, (article_id,))
        return rows[0]['abbreviation'] if rows else None

    def update_analysis_states_batch(self, updates: List[Dict[str, Any]]) -> int:
        """Update analysis records with state information."""
        if not updates:
            return 0

        query = """
        UPDATE ArticleDuplicateAnalyses
        SET articleNewState = ?, articleApprovedState = ?, sameStateFlag = ?, updatedAt = datetime('now')
        WHERE id = ?
        """

        params_list = [
            (
                update['articleNewState'],
                update['articleApprovedState'],
                update['sameStateFlag'],
                update['id']
            )
            for update in updates
        ]

        return self.execute_many(query, params_list)

    def get_state_processing_stats(self) -> Dict[str, int]:
        """Get statistics about state processing."""
        queries = {
            'same_state_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE sameStateFlag = 1 AND articleNewState != ''",
            'different_state_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE sameStateFlag = 0 AND articleNewState != '' AND articleApprovedState != ''",
            'missing_state_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE articleNewState = '' OR articleApprovedState = ''"
        }

        stats = {}
        conn = self.get_connection()
        cursor = conn.cursor()

        for key, query in queries.items():
            cursor.execute(query)
            stats[key] = cursor.fetchone()[0]

        return stats

    def get_analysis_records_for_url_update(self) -> List[Dict[str, Any]]:
        """Get analysis records that need URL check information updated."""
        query = """
        SELECT id, articleIdNew, articleIdApproved
        FROM ArticleDuplicateAnalyses
        WHERE urlCheck = 0
        """
        return self.execute_query(query)

    def get_article_url(self, article_id: int) -> Optional[str]:
        """Get URL for an article."""
        query = """
        SELECT url
        FROM Articles
        WHERE id = ?
        """
        rows = self.execute_query(query, (article_id,))
        return rows[0]['url'] if rows else None

    def update_analysis_url_check_batch(self, updates: List[Dict[str, Any]]) -> int:
        """Update analysis records with URL check results."""
        if not updates:
            return 0

        query = """
        UPDATE ArticleDuplicateAnalyses
        SET urlCheck = ?, updatedAt = datetime('now')
        WHERE id = ?
        """

        params_list = [
            (
                update['urlCheck'],
                update['id']
            )
            for update in updates
        ]

        return self.execute_many(query, params_list)

    def get_url_check_processing_stats(self) -> Dict[str, int]:
        """Get statistics about URL check processing."""
        queries = {
            'url_match_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE urlCheck = 1",
            'url_no_match_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE urlCheck = 0"
        }

        stats = {}
        conn = self.get_connection()
        cursor = conn.cursor()

        for key, query in queries.items():
            cursor.execute(query)
            stats[key] = cursor.fetchone()[0]

        return stats

    def get_analysis_records_for_content_hash_update(self) -> List[Dict[str, Any]]:
        """Get analysis records that need content hash information updated."""
        query = """
        SELECT id, articleIdNew, articleIdApproved
        FROM ArticleDuplicateAnalyses
        WHERE contentHash = 0
        """
        return self.execute_query(query)

    def get_analysis_records_for_content_hash_update_with_contents(self, limit: int) -> List[Dict[str, Any]]:
        """Get analysis records with content for bulk content hash processing."""
        query = """
        SELECT
            adr.id,
            adr.articleIdNew,
            adr.articleIdApproved,
            aa1.headlineForPdfReport AS headlineNew,
            aa1.textForPdfReport AS textNew,
            aa2.headlineForPdfReport AS headlineApproved,
            aa2.textForPdfReport AS textApproved
        FROM ArticleDuplicateAnalyses adr
        JOIN ArticleApproveds aa1 ON aa1.articleId = adr.articleIdNew
        JOIN ArticleApproveds aa2 ON aa2.articleId = adr.articleIdApproved
        WHERE adr.contentHash = 0
        LIMIT ?
        """
        return self.execute_query(query, (limit,))

    def get_article_content(self, article_id: int) -> Optional[str]:
        """Get content for an article from ArticleApproveds table."""
        query = """
        SELECT textForPdfReport
        FROM ArticleApproveds
        WHERE articleId = ? AND isApproved = 1
        LIMIT 1
        """
        rows = self.execute_query(query, (article_id,))
        return rows[0]['textForPdfReport'] if rows else None

    def update_analysis_content_hash_batch(self, updates: List[Dict[str, Any]]) -> int:
        """Update analysis records with content hash results."""
        if not updates:
            return 0

        query = """
        UPDATE ArticleDuplicateAnalyses
        SET contentHash = ?, updatedAt = datetime('now')
        WHERE id = ?
        """

        params_list = [
            (
                update['contentHash'],
                update['id']
            )
            for update in updates
        ]

        return self.execute_many(query, params_list)

    def get_content_hash_processing_stats(self) -> Dict[str, int]:
        """Get statistics about content hash processing."""
        queries = {
            'content_match_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE contentHash = 1",
            'content_no_match_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE contentHash = 0"
        }

        stats = {}
        conn = self.get_connection()
        cursor = conn.cursor()

        for key, query in queries.items():
            cursor.execute(query)
            stats[key] = cursor.fetchone()[0]

        return stats

    def get_analysis_records_for_embedding_update(self) -> List[Dict[str, Any]]:
        """Get analysis records that need embedding similarity analysis."""
        query = """
        SELECT id, articleIdNew, articleIdApproved
        FROM ArticleDuplicateAnalyses
        WHERE embeddingSearch = 0
        """
        return self.execute_query(query)

    def update_analysis_embedding_batch(self, updates: List[Dict[str, Any]]) -> int:
        """Update analysis records with embedding similarity results (float values)."""
        if not updates:
            return 0

        query = """
        UPDATE ArticleDuplicateAnalyses
        SET embeddingSearch = ?, updatedAt = datetime('now')
        WHERE id = ?
        """

        params_list = [
            (
                float(update['embeddingSearch']),  # Ensure float type
                update['id']
            )
            for update in updates
        ]

        return self.execute_many(query, params_list)

    def get_embedding_processing_stats(self) -> Dict[str, int]:
        """Get statistics about embedding processing."""
        queries = {
            'high_similarity_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE embeddingSearch > 0.8",
            'medium_similarity_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE embeddingSearch BETWEEN 0.5 AND 0.8",
            'low_similarity_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE embeddingSearch < 0.5 AND embeddingSearch > 0",
            'processed_count': "SELECT COUNT(*) FROM ArticleDuplicateAnalyses WHERE embeddingSearch > 0"
        }

        stats = {}
        conn = self.get_connection()
        cursor = conn.cursor()

        for key, query in queries.items():
            cursor.execute(query)
            stats[key] = cursor.fetchone()[0]

        return stats

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()