"""
Database Configuration

PostgreSQL 및 Redis 연결 설정
"""

from typing import Generator

import redis.asyncio as redis
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from .config import BACKEND_ROOT, settings


def normalize_database_url(raw_url: str) -> str:
    """Make sqlite URLs stable regardless of the current working directory."""
    if raw_url.startswith("sqlite:///") and not raw_url.startswith("sqlite:////"):
        relative_path = raw_url.removeprefix("sqlite:///")
        normalized_path = str((BACKEND_ROOT / relative_path).resolve())
        return f"sqlite:///{normalized_path}"
    return raw_url

# 데이터베이스 엔진 (SQLite/PostgreSQL 지원)
database_url = normalize_database_url(settings.database_url)
if database_url.startswith("postgresql+asyncpg://"):
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(
    database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=300,
)

# 동기 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# SQLAlchemy Base 클래스
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """데이터베이스 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Redis 연결 풀
redis_pool = None


async def get_redis_pool():
    """Redis 연결 풀 생성"""
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20
        )
    return redis_pool


async def get_redis() -> redis.Redis:
    """Redis 클라이언트 반환"""
    pool = await get_redis_pool()
    return redis.Redis(connection_pool=pool)


async def close_db_connections():
    """데이터베이스 연결 종료"""
    global redis_pool
    
    # PostgreSQL 연결 종료 (임시 비활성화)
    # if engine:
    #     await engine.dispose()
    
    # Redis 연결 풀 종료
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None
