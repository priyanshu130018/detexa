"""
database/db.py
─────────────────────────────────────────────────────────────────────────────
SQLAlchemy async-compatible engine + session factory.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session then closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
