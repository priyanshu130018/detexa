"""
app/core/logging.py
─────────────────────────────────────────────────────────────────────────────
Structured logging configuration driven by centralized settings.
Supports Loguru with standard library logging fallback.
"""

from pathlib import Path
import re
import sys
import logging

from app.core.config import settings

# Ensure log directory exists
log_file = Path(settings.log_file_path)
log_file.parent.mkdir(parents=True, exist_ok=True)


class JWTTokenRedactionFilter(logging.Filter):
    """
    Prevents JWT tokens, auth headers, and sensitive query parameters
    from being exposed in access logs (e.g., uvicorn.access) and application logs.
    """
    TOKEN_QUERY_REGEX = re.compile(r'([?&](?:token|access_token|auth|bearer)=)[^&\s]+', re.IGNORECASE)
    JWT_STRING_REGEX = re.compile(r'ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+')
    BEARER_HEADER_REGEX = re.compile(r'Bearer\s+[A-Za-z0-9_\-\.]+', re.IGNORECASE)

    @classmethod
    def redact(cls, text: str) -> str:
        if not isinstance(text, str):
            return text
        text = cls.TOKEN_QUERY_REGEX.sub(r'\1[REDACTED]', text)
        text = cls.BEARER_HEADER_REGEX.sub(r'Bearer [REDACTED]', text)
        text = cls.JWT_STRING_REGEX.sub(r'[REDACTED_TOKEN]', text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(self.redact(a) if isinstance(a, str) else a for a in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: self.redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
        return True


def apply_security_log_filters():
    """Apply the redaction filter to standard library and uvicorn loggers."""
    redaction_filter = JWTTokenRedactionFilter()
    target_loggers = [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "detexa",
        "detexa.realtime",
        "",  # root logger
    ]
    for logger_name in target_loggers:
        lgr = logging.getLogger(logger_name)
        if not any(isinstance(f, JWTTokenRedactionFilter) for f in lgr.filters):
            lgr.addFilter(redaction_filter)
        for handler in lgr.handlers:
            if not any(isinstance(f, JWTTokenRedactionFilter) for f in handler.filters):
                handler.addFilter(redaction_filter)


try:
    from loguru import logger as loguru_logger
    loguru_logger.remove()
    loguru_logger.configure(
        patcher=lambda record: record.update(message=JWTTokenRedactionFilter.redact(record["message"]))
    )
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
        ch.addFilter(JWTTokenRedactionFilter())
        formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)

apply_security_log_filters()

__all__ = ["logger", "JWTTokenRedactionFilter", "apply_security_log_filters"]
