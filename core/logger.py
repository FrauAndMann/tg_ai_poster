"""
Logging module using loguru.

Provides structured logging with file rotation and console output.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# Remove default handler
logger.remove()

# Flag to track if logger has been configured
_configured = False


def setup_logger(
    log_level: str = "INFO",
    log_dir: str | Path = "logs",
    log_file: str = "tg_poster_{time:YYYY-MM-DD}.log",
    rotation: str = "10 MB",
    retention: str = "30 days",
    compression: str = "zip",
    json_format: bool = False,
    console_output: bool = True,
) -> None:
    """
    Configure loguru logger for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        log_file: Log file name pattern
        rotation: When to rotate log files
        retention: How long to keep old logs
        compression: Compression format for rotated logs
        json_format: Use JSON format for log entries
        console_output: Also output to console
    """
    global _configured

    if _configured:
        logger.warning("Logger already configured, skipping setup")
        return

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Console format - colorful and human-readable
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # File format - detailed and parseable
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    # JSON format for structured logging
    json_format_str = (
        '{{"timestamp": "{time:YYYY-MM-DDTHH:mm:ss.SSSZ}", '
        '"level": "{level}", '
        '"logger": "{name}", '
        '"function": "{function}", '
        '"line": {line}, '
        '"message": "{message}"}}'
    )

    # Add console handler
    if console_output:
        logger.add(
            sys.stderr,
            format=console_format,
            level=log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    # Add file handler
    logger.add(
        log_path / log_file,
        format=json_format_str if json_format else file_format,
        level=log_level,
        rotation=rotation,
        retention=retention,
        compression=compression,
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
        serialize=json_format,
    )

    # Add error file handler for errors only
    logger.add(
        log_path / "errors_{time:YYYY-MM-DD}.log",
        format=file_format,
        level="ERROR",
        rotation=rotation,
        retention=retention,
        compression=compression,
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
        filter=lambda record: record["level"].name == "ERROR",
    )

    _configured = True
    logger.info(f"Logger configured with level={log_level}, log_dir={log_path}")


def get_logger(name: Optional[str] = None) -> "logger":
    """
    Get a logger instance with optional name binding.

    Args:
        name: Optional name to bind to the logger

    Returns:
        Configured logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


class LogContext:
    """
    Context manager for adding temporary context to log messages.

    Usage:
        with LogContext(post_id=123, status="generating"):
            logger.info("Processing post")
    """

    def __init__(self, **kwargs):
        self.context = kwargs
        self.handle = None

    def __enter__(self):
        self.handle = logger.bind(**self.context)
        return self.handle

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.exception(f"Exception in context: {exc_val}")
        return False


def log_function_call(func_name: str, **kwargs):
    """
    Decorator-like function to log function calls with parameters.

    Args:
        func_name: Name of the function being called
        **kwargs: Parameters to log
    """
    params = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
    logger.debug(f"Calling {func_name}({params})")


def log_execution_time(func_name: str, duration: float):
    """
    Log function execution time.

    Args:
        func_name: Name of the function
        duration: Execution time in seconds
    """
    logger.debug(f"{func_name} executed in {duration:.3f}s")


# Convenience exports
__all__ = [
    "logger",
    "setup_logger",
    "get_logger",
    "LogContext",
    "log_function_call",
    "log_execution_time",
]
