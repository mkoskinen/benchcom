import asyncpg
from typing import Optional
from .config import settings


class Database:
    """Database connection pool manager"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create database connection pool"""
        self.pool = await asyncpg.create_pool(
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            min_size=5,
            max_size=20,
        )

    async def disconnect(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()

    async def execute(self, query: str, *args):
        """Execute a query without returning results"""
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def fetch(self, query: str, *args):
        """Fetch multiple rows"""
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        """Fetch a single row"""
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """Fetch a single value"""
        async with self.pool.acquire() as connection:
            return await connection.fetchval(query, *args)


db = Database()
