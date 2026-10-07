"""
app/core/logging.py
─────────────────────────────────────────────────────────────────────────────
Structured logging configuration driven by centralized settings.
Supports Loguru with standard library logging fallback.
"""

from pathlib import Path
import sys
import logging

from app.core.config import settings

# Ensure log directory exists
log_file = Path(settings.log_file_path)
log_file.parent.mkdir(parents=True, exist_ok=True)

try:
    from loguru import logger as loguru_logger
    loguru_logger.remove()
    loguru_logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level.upper(),
    )
    loguru_logger.add(
        str(log_file),
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
        level="DEBUG",
        enqueue=True,
    )
    logger = loguru_logger
except ImportError:
    # Standard library fallback
    logger = logging.getLogger("detexa")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    if not logger.handlers:
        ch = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)

__all__ = ["logger"]
