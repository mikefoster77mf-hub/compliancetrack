import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# ── Construct DATABASE_URL from Render env vars ────────────────────────────
# Render gives us DB_HOST, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB.
# asyncpg needs the 'postgresql+asyncpg://' dialect (not raw 'postgresql://').
DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("POSTGRES_USER", "myuser")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "mypassword")
DB_NAME = os.getenv("POSTGRES_DB", "myapp")
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

# ── Async engine ───────────────────────────────────────────────────────────
engine = create_async_engine(
    DATABASE_URL,
    echo=False,           # flip to True temporarily for Render log debugging
    pool_pre_ping=True,   # handles dropped connections from Render's network
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ────────────────────────────────────────────────────────
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # avoids DetachedInstanceError on post-commit access
)

# ── Declarative base for ORM models ───────────────────────────────────────
class Base(DeclarativeBase):
    pass

# ── FastAPI dependency ─────────────────────────────────────────────────────
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Scoped async session per request. Auto-close on exit.

    Usage in a route:

        from fastapi import Depends
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        @app.get("/api/v1/vendors")
        async def list_vendors(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(VendorModel).order_by(VendorModel.name))
            vendors = result.scalars().all()
            return [{"id": v.id, "name": v.name, "email": v.email} for v in vendors]
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
