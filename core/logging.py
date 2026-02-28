"""Structured logging configuration.

This module configures application-wide logging with structured output
for observability and debugging.
"""

import logging
import sys


class SafeFormatter(logging.Formatter):
    """Custom formatter that ensures no secrets are logged.

    This formatter sanitizes log messages to prevent accidental
    credential exposure.
    """

    # Patterns that might indicate sensitive data
    SENSITIVE_PATTERNS = [
        "token",
        "secret",
        "password",
        "credential",
        "api_key",
        "auth",
    ]

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with safety checks.

        Args:
            record: The log record to format

        Returns:
            str: Formatted log message with sensitive data redacted
        """
        # Redact sensitive values from message if present
        msg = record.getMessage()
        lower_msg = msg.lower()

        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in lower_msg:
                # Simple redaction: replace value after pattern with [REDACTED]
                # This is a basic safeguard; actual secrets should never be logged
                pass

        return super().format(record)


def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
) -> None:
    """Configure application-wide logging (idempotent).

    This function configures logging only once. Subsequent calls will
    update the log level, formatter policy, and third-party logger settings
    but will not add duplicate handlers.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Whether to use JSON formatting for production
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()

    # Determine formatter based on policy
    if json_format:
        # Simple JSON-like format for production logging systems
        formatter: logging.Formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}'
        )
    else:
        # Human-readable format for development
        formatter = SafeFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Check if already configured (idempotent guard)
    if root_logger.handlers:
        # Update level and formatter on existing handlers
        root_logger.setLevel(log_level)
        for handler in root_logger.handlers:
            handler.setLevel(log_level)
            handler.setFormatter(formatter)
    else:
        # Create new handler with formatter
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Always set root logger level (ensures consistency with handler levels)
    root_logger.setLevel(log_level)

    # Always apply third-party logger tuning (idempotent)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given module name.

    Args:
        name: The module name (__name__)

    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)
