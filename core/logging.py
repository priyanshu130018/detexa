"""
core/logging.py
─────────────────────────────────────────────────────────────────────────────
Structured logging via Loguru. Import `logger` everywhere in the project.
"""

import sys
from loguru import logger

logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "logs/detexa.log",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    level="DEBUG",
    enqueue=True,
)

__all__ = ["logger"]
