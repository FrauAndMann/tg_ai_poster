"""
Database connection and session management.

Provides async SQLAlchemy engine and session handling.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from core.logger import get_logger
from memory.models import Base

logger = get_logger(__name__)


class Database:
    """
    Database manager with async support.

    Handles connection pooling, session management, and initialization.
    """

    def __init__(
        self,
        db_url: str,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
    ) -> None:
        """
        Initialize database manager.

        Args:
            db_url: Database connection URL
            echo: Whether to echo SQL statements
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
        """
        self.db_url = db_url
        self.echo = echo
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

        # Pool settings
        self.pool_size = pool_size
        self.max_overflow = max_overflow

    def _get_engine_kwargs(self) -> dict:
        """Get engine kwargs based on database type."""
        kwargs = {
            "echo": self.echo,
        }

        # SQLite in-memory databases need special handling to share connection
        if self.db_url.startswith("sqlite"):
            # Check if it's an in-memory database
            if ":memory:" in self.db_url:
                # Use StaticPool with single connection for in-memory databases
                # This ensures all operations share the same database
                from sqlalchemy.pool import StaticPool

                kwargs["poolclass"] = StaticPool
                kwargs["connect_args"] = {"check_same_thread": False}
            else:
                # Regular SQLite file database
                kwargs["poolclass"] = NullPool
        else:
            # PostgreSQL and others use connection pooling
            kwargs.update(
                {
                    "pool_size": self.pool_size,
                    "max_overflow": self.max_overflow,
                    "pool_pre_ping": True,
                    "pool_recycle": 3600,
                }
            )

        return kwargs

    async def init(self) -> None:
        """Initialize database engine and create tables."""
        if self._engine is not None:
            logger.warning("Database already initialized")
            return

        # Convert SQLite URL to async format
        db_url = self.db_url
        if db_url.startswith("sqlite://"):
            db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
        elif db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        logger.info(
            f"Initializing database: {db_url.split('@')[-1] if '@' in db_url else db_url}"
        )

        self._engine = create_async_engine(db_url, **self._get_engine_kwargs())

        # Create session factory
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # Create tables
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized and tables created")

    async def close(self) -> None:
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connections closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session as a context manager.

        Yields:
            AsyncSession: Database session

        Usage:
            async with db.session() as session:
                result = await session.execute(query)
        """
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call init() first.")

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def get_session(self) -> AsyncSession:
        """
        Get a database session (must be manually closed).

        Returns:
            AsyncSession: Database session

        Note:
            Prefer using the session() context manager for automatic cleanup.
        """
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call init() first.")

        return self._session_factory()

    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine."""
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._engine

    async def health_check(self) -> bool:
        """
        Check database connection health.

        Returns:
            bool: True if database is healthy
        """
        try:
            async with self.session() as session:
                await session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database instance
_db: Database | None = None


async def init_database(db_url: str, echo: bool = False) -> Database:
    """
    Initialize the global database instance.

    Args:
        db_url: Database connection URL
        echo: Whether to echo SQL statements

    Returns:
        Database: Initialized database instance
    """
    global _db
    _db = Database(db_url, echo=echo)
    await _db.init()
    return _db


async def close_database() -> None:
    """Close the global database instance."""
    global _db
    if _db:
        await _db.close()
        _db = None


@lru_cache()
def get_database() -> Database:
    """
    Get the global database instance.

    Returns:
        Database: Database instance

    Raises:
        RuntimeError: If database is not initialized
    """
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI-style dependency for getting database sessions.

    Yields:
        AsyncSession: Database session
    """
    db = get_database()
    async with db.session() as session:
        yield session
