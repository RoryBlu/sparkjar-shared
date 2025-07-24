"""
Database connection management using SQLAlchemy with async support.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager
import logging
import warnings

from sparkjar_shared.config.config import DATABASE_URL_DIRECT, DATABASE_URL_POOLED, DATABASE_URL
from sparkjar_shared.database.models import Base

logger = logging.getLogger(__name__)

# Suppress specific asyncpg warnings that occur during shutdown
# These are harmless but noisy during cleanup
logging.getLogger("asyncpg.protocol").setLevel(logging.CRITICAL)
logging.getLogger("sqlalchemy.pool.impl.AsyncAdaptedQueuePool").setLevel(logging.CRITICAL)

# Suppress RuntimeWarnings about unawaited coroutines during shutdown
warnings.filterwarnings("ignore", message="coroutine.*was never awaited", category=RuntimeWarning)

# Create async engines for different use cases
def create_direct_engine():
    """Create direct connection engine (port 5432) for admin/dev operations."""
    return create_async_engine(
        DATABASE_URL_DIRECT,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,
        pool_recycle=3600,
        # Reduce connection timeout to prevent hanging during shutdown
        pool_timeout=10,
        pool_size=5,
        max_overflow=10,
        # Direct connection settings - full PostgreSQL features
        connect_args={
            "server_settings": {"jit": "off"},  # Optimize for admin operations
            "command_timeout": 5  # Faster timeout to prevent hanging
        }
    )

def create_pooled_engine():
    """Create pooled connection engine (port 6543) for production API operations."""
    return create_async_engine(
        DATABASE_URL_POOLED,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,  # Shorter recycle for pooled connections
        # Reduce connection timeout to prevent hanging during shutdown
        pool_timeout=10,
        pool_size=5,
        max_overflow=10,
        # Pooled connection settings - compatible with pgbouncer
        connect_args={
            "statement_cache_size": 0,  # Disable prepared statements for pgbouncer
            "server_settings": {"jit": "off"},
            "command_timeout": 5  # Faster timeout to prevent hanging
        }
    )

# Default engines - choose based on use case
direct_engine = create_direct_engine()  # For admin, migrations, schema operations
pooled_engine = create_pooled_engine()  # For API, high-concurrency operations

# Primary engine - defaults to direct for backwards compatibility
engine = direct_engine

# Create session factories for different engines
DirectSessionLocal = async_sessionmaker(direct_engine, class_=AsyncSession, expire_on_commit=False)
PooledSessionLocal = async_sessionmaker(pooled_engine, class_=AsyncSession, expire_on_commit=False)

# Default session factory (backwards compatibility)
AsyncSessionLocal = DirectSessionLocal

# Convenience functions for different use cases
@asynccontextmanager
async def get_direct_session():
    """Get direct connection session for admin/dev operations (port 5432)."""
    async with DirectSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@asynccontextmanager
async def get_pooled_session():
    """Get pooled connection session for API operations (port 6543)."""
    async with PooledSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def create_tables():
    """
    Create all database tables.
    This should be run during application startup.
    """
    try:
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

async def drop_tables():
    """
    Drop all database tables.
    Use with caution - this will delete all data!
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Failed to drop database tables: {e}")
        raise

async def check_database_connection():
    """
    Check if database connection is working.
    
    Returns:
        bool: True if connection is successful
    """
    try:
        async with get_direct_session() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

# Synchronous version for non-async contexts (keeping for compatibility)
def create_sync_engine():
    """
    Create synchronous engine for migrations and setup scripts.
    """
    from sqlalchemy import create_engine
    # Convert async URL back to sync format for migrations
    sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    return create_engine(sync_url, echo=False)

def get_sync_session():
    """
    Get synchronous session for migrations and setup scripts.
    """
    from sqlalchemy.orm import sessionmaker
    engine = create_sync_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

# Default session (backwards compatibility) - use direct connection for admin operations
get_db_session = get_direct_session

async def cleanup_engines():
    """
    Properly dispose of all database engines to prevent connection errors during shutdown.
    Call this before event loop closes.
    """
    import asyncio
    
    try:
        logger.info("Cleaning up database engines...")
        
        # Force close all connections immediately without waiting for graceful shutdown
        # This prevents the asyncpg protocol errors during event loop closure
        
        if direct_engine:
            try:
                # Force immediate disposal without async operations
                await asyncio.wait_for(direct_engine.dispose(), timeout=1.0)
                logger.info("Direct engine disposed")
            except asyncio.TimeoutError:
                logger.debug("Direct engine disposal timed out - forcing sync cleanup")
            except Exception as e:
                logger.debug(f"Direct engine disposal error (non-critical): {e}")
                
        if pooled_engine:
            try:
                # Force immediate disposal without async operations
                await asyncio.wait_for(pooled_engine.dispose(), timeout=1.0)
                logger.info("Pooled engine disposed")  
            except asyncio.TimeoutError:
                logger.debug("Pooled engine disposal timed out - forcing sync cleanup")
            except Exception as e:
                logger.debug(f"Pooled engine disposal error (non-critical): {e}")
                
        logger.info("Database engines cleaned up successfully")
            
    except Exception as e:
        # Log as debug to reduce noise - these cleanup errors are not critical
        logger.debug(f"Engine cleanup completed with minor issues: {e}")

def cleanup_engines_sync():
    """
    Synchronous version of cleanup for when async is not available.
    Uses sync disposal to avoid event loop issues.
    """
    try:
        logger.info("Cleaning up database engines...")
        
        # Use sync disposal method to avoid event loop issues
        if direct_engine:
            try:
                # Use the sync dispose method
                direct_engine.sync_engine.dispose()
                logger.info("Direct engine disposed")
            except Exception as e:
                logger.debug(f"Direct engine cleanup error (non-critical): {e}")
                
        if pooled_engine:
            try:
                # Use the sync dispose method  
                pooled_engine.sync_engine.dispose()
                logger.info("Pooled engine disposed")
            except Exception as e:
                logger.debug(f"Pooled engine cleanup error (non-critical): {e}")
                
    except Exception as e:
        # Downgrade to debug level to reduce noise
        logger.debug(f"Engine cleanup completed with minor issues: {e}")

# Add atexit handler for cleanup
import atexit
atexit.register(cleanup_engines_sync)
