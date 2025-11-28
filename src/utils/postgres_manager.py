"""
PostgreSQL Manager for MAESTRO

Provides async PostgreSQL operations using asyncpg.
"""

import logging
import os
from typing import Dict, Any, List, Optional
import asyncpg

logger = logging.getLogger(__name__)


class PostgresManager:
    """
    Manages PostgreSQL connections and operations.

    Uses asyncpg for async database operations.
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        database: str = None,
        user: str = None,
        password: str = None
    ):
        """
        Initialize PostgreSQL connection manager.

        Args:
            host: PostgreSQL host (default: from env or 'localhost')
            port: PostgreSQL port (default: from env or 5432)
            database: Database name (default: from env or 'maestro')
            user: Database user (default: from env or 'postgres')
            password: Database password (default: from env)
        """
        self.host = host or os.getenv('POSTGRES_HOST', 'localhost')
        self.port = port or int(os.getenv('POSTGRES_PORT', '5432'))
        self.database = database or os.getenv('POSTGRES_DB', 'maestro')
        self.user = user or os.getenv('POSTGRES_USER', 'postgres')
        self.password = password or os.getenv('POSTGRES_PASSWORD', 'postgres')

        self.pool: Optional[asyncpg.Pool] = None

        logger.info(
            f"PostgreSQL Manager initialized: {self.user}@{self.host}:{self.port}/{self.database}"
        )

    async def connect(self):
        """Establish PostgreSQL connection pool"""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    min_size=2,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("✅ Connected to PostgreSQL")
            except Exception as e:
                logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
                raise

    async def close(self):
        """Close PostgreSQL connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Disconnected from PostgreSQL")

    async def execute(self, query: str, *args) -> str:
        """
        Execute a SQL query that doesn't return rows.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Status string from the database
        """
        await self.connect()

        async with self.pool.acquire() as conn:
            result = await conn.execute(query, *args)
            return result

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

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
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

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
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
        await self.connect()

        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def executemany(self, query: str, args_list: List[tuple]) -> None:
        """
        Execute a query multiple times with different parameters.

        Args:
            query: SQL query
            args_list: List of parameter tuples
        """
        await self.connect()

        async with self.pool.acquire() as conn:
            await conn.executemany(query, args_list)

    async def transaction(self):
        """
        Start a transaction context.

        Usage:
            async with pg.transaction():
                await pg.execute("INSERT ...")
                await pg.execute("UPDATE ...")
        """
        await self.connect()
        return self.pool.acquire()

    async def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.

        Args:
            table_name: Name of the table

        Returns:
            True if table exists
        """
        result = await self.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = $1
            )
            """,
            table_name
        )
        return result

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get PostgreSQL statistics.

        Returns:
            Dict with statistics
        """
        await self.connect()

        # Get database size
        db_size = await self.fetchval(
            "SELECT pg_size_pretty(pg_database_size($1))",
            self.database
        )

        # Get table count
        table_count = await self.fetchval(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )

        # Get connection pool stats
        pool_size = self.pool.get_size() if self.pool else 0
        pool_free = self.pool.get_idle_size() if self.pool else 0

        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "database_size": db_size,
            "table_count": table_count,
            "pool_size": pool_size,
            "pool_free": pool_free,
            "pool_in_use": pool_size - pool_free
        }


# Global instance
_postgres_manager: Optional[PostgresManager] = None


async def get_postgres() -> PostgresManager:
    """
    Get global PostgreSQL manager instance.

    Returns:
        PostgresManager instance
    """
    global _postgres_manager

    if _postgres_manager is None:
        _postgres_manager = PostgresManager()
        await _postgres_manager.connect()

    return _postgres_manager


# Standalone test
async def test_postgres_manager():
    """Test PostgreSQL manager"""
    logger.info("=" * 80)
    logger.info("TEST: PostgreSQL Manager")
    logger.info("=" * 80)

    pg = PostgresManager()
    await pg.connect()

    try:
        # Test connection
        logger.info("\n1. Testing connection...")
        result = await pg.fetchval("SELECT 1")
        assert result == 1
        logger.info("   ✅ Connection successful")

        # Test table check
        logger.info("\n2. Checking if tables exist...")
        exists = await pg.table_exists("technical_components")
        logger.info(f"   technical_components exists: {exists}")

        # Get stats
        logger.info("\n3. Getting stats...")
        stats = await pg.get_stats()
        for key, value in stats.items():
            logger.info(f"   {key}: {value}")

        logger.info("\n✅ All tests passed")

    finally:
        await pg.close()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_postgres_manager())
