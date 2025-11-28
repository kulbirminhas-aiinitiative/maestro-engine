"""
SQLite Manager for MAESTRO (Alternative to PostgreSQL for testing)

Provides async SQLite operations using aiosqlite.
"""

import logging
import os
import aiosqlite
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SQLiteManager:
    """
    Manages SQLite connections and operations.

    Uses aiosqlite for async database operations.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize SQLite connection manager.

        Args:
            db_path: Path to SQLite database file (default: maestro_kb.db)
        """
        if db_path is None:
            # Use project data directory
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "maestro_kb.db")

        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

        logger.info(f"SQLite Manager initialized: {self.db_path}")

    async def connect(self):
        """Establish SQLite connection"""
        if self.conn is None:
            try:
                self.conn = await aiosqlite.connect(self.db_path)
                self.conn.row_factory = aiosqlite.Row
                logger.info(f"✅ Connected to SQLite: {self.db_path}")
            except Exception as e:
                logger.error(f"❌ Failed to connect to SQLite: {e}")
                raise

    async def close(self):
        """Close SQLite connection"""
        if self.conn:
            await self.conn.close()
            self.conn = None
            logger.info("Disconnected from SQLite")

    async def execute(self, query: str, *args) -> str:
        """
        Execute a SQL query that doesn't return rows.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Status string
        """
        await self.connect()
        await self.conn.execute(query, args)
        await self.conn.commit()
        return "OK"

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """
        Fetch multiple rows from a SQL query.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            List of rows as dictionaries
        """
        await self.connect()
        async with self.conn.execute(query, args) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """
        Fetch a single row from a SQL query.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Row as dictionary or None
        """
        await self.connect()
        async with self.conn.execute(query, args) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetchval(self, query: str, *args) -> Any:
        """
        Fetch a single value from a SQL query.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Single value or None
        """
        row = await self.fetchrow(query, *args)
        if row:
            return list(row.values())[0]
        return None

    async def executemany(self, query: str, args_list: List[tuple]) -> None:
        """
        Execute a query multiple times with different parameters.

        Args:
            query: SQL query
            args_list: List of parameter tuples
        """
        await self.connect()
        await self.conn.executemany(query, args_list)
        await self.conn.commit()

    async def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.

        Args:
            table_name: Name of the table

        Returns:
            True if table exists
        """
        result = await self.fetchval(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            table_name
        )
        return result > 0

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get SQLite statistics.

        Returns:
            Dict with statistics
        """
        await self.connect()

        # Get database size
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        db_size_mb = db_size / (1024 * 1024)

        # Get table count
        table_count = await self.fetchval(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        )

        return {
            "db_path": self.db_path,
            "database_size_mb": round(db_size_mb, 2),
            "table_count": table_count
        }


# Global instance
_sqlite_manager: Optional[SQLiteManager] = None


async def get_sqlite() -> SQLiteManager:
    """
    Get global SQLite manager instance.

    Returns:
        SQLiteManager instance
    """
    global _sqlite_manager

    if _sqlite_manager is None:
        _sqlite_manager = SQLiteManager()
        await _sqlite_manager.connect()

    return _sqlite_manager


# Standalone test
async def test_sqlite_manager():
    """Test SQLite manager"""
    logger.info("=" * 80)
    logger.info("TEST: SQLite Manager")
    logger.info("=" * 80)

    db = SQLiteManager()
    await db.connect()

    try:
        # Test connection
        logger.info("\n1. Testing connection...")
        result = await db.fetchval("SELECT 1")
        assert result == 1
        logger.info("   ✅ Connection successful")

        # Create test table
        logger.info("\n2. Creating test table...")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)"
        )
        logger.info("   ✅ Table created")

        # Insert data
        logger.info("\n3. Inserting data...")
        await db.execute("INSERT INTO test_table (name) VALUES (?)", "test_value")
        await db.conn.commit()
        logger.info("   ✅ Data inserted")

        # Query data
        logger.info("\n4. Querying data...")
        rows = await db.fetch("SELECT * FROM test_table")
        logger.info(f"   Found {len(rows)} rows")

        # Get stats
        logger.info("\n5. Getting stats...")
        stats = await db.get_stats()
        for key, value in stats.items():
            logger.info(f"   {key}: {value}")

        # Cleanup
        await db.execute("DROP TABLE test_table")

        logger.info("\n✅ All tests passed")

    finally:
        await db.close()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_sqlite_manager())
