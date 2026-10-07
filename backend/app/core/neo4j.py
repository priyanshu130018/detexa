"""
app/core/neo4j.py
─────────────────────────────────────────────────────────────────────────────
Neo4j Graph Database connection manager and session handler.
Reads configuration from centralized settings (.env).
Provides connection pooling, health verification, and graceful degradation.
"""

from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger

try:
    from neo4j import Driver, GraphDatabase, Session
except ImportError:
    Driver = None
    GraphDatabase = None
    Session = None

_driver: Optional[Any] = None


def get_neo4j_driver() -> Optional[Any]:
    """
    Returns the thread-safe Neo4j driver singleton.
    Returns None if Neo4j is disabled or unreachable.
    """
    global _driver
    if not settings.neo4j_enabled or GraphDatabase is None:
        return None

    if _driver is None:
        try:
            auth = (settings.neo4j_user, settings.neo4j_password)
            _driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=auth,
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=5.0,
            )
            # Verify connectivity
            _driver.verify_connectivity()
            logger.info(f"Successfully connected to Neo4j Graph Database at {settings.neo4j_uri}")
        except Exception as exc:
            logger.warning(f"Neo4j connection failed ({exc}). Running with graph features in fallback mode.")
            _driver = None

    return _driver


def close_neo4j_driver():
    """Closes the active Neo4j driver connection pool."""
    global _driver
    if _driver is not None:
        try:
            _driver.close()
            logger.info("Closed Neo4j driver connection pool.")
        except Exception as exc:
            logger.error(f"Error closing Neo4j driver: {exc}")
        finally:
            _driver = None
