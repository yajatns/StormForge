"""
Database configuration and session management
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


async def get_db() -> AsyncSession:
    """Database session dependency"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database"""
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they're registered
            from app.models import user, job, target_group, audit_log  # noqa
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


async def close_db():
    """Close database connections"""
    await engine.dispose()
    logger.info("Database connections closed")