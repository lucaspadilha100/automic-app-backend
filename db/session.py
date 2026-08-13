from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.core.config import settings

# The production defaults are sized for serverless, where many short-lived
# instances each hold their own pool and a big one would exhaust the database's
# connection limit. On an always-on host the opposite is true: one long-lived
# process serves every request, so a larger pool means requests reuse warm
# connections instead of queueing. Override with DB_POOL_SIZE / DB_MAX_OVERFLOW.
_pool_size = settings.DB_POOL_SIZE or (2 if settings.is_production else 10)
_max_overflow = settings.DB_MAX_OVERFLOW or (3 if settings.is_production else 20)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_recycle=300,
    echo=settings.DEBUG,
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
