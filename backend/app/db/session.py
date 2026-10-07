"""
app/db/session.py
─────────────────────────────────────────────────────────────────────────────
SQLAlchemy database engine and session factory with centralized configuration.
Supports PostgreSQL (local or cloud Neon with SSL), SQLite, etc.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

is_sqlite = settings.database_url.startswith("sqlite")

engine_kwargs = {"echo": settings.db_echo}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_pre_ping": settings.db_pool_pre_ping,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_recycle": settings.db_pool_recycle,
    })

engine = create_engine(settings.database_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency yielding a database session with rollback on exception and guaranteed close."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
