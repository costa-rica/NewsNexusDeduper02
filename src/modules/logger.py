"""
Unified logging module for NewsNexusDeduper02.
Implements LOGGING_PYTHON_V05 specification using Loguru.
"""

import os
import sys
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global flag to track if logger has been configured
_logger_configured = False


def _validate_required_env_vars():
    """
    Validate required environment variables at startup.

    Missing required variables trigger immediate fatal errors.

    Raises:
        SystemExit: If any required variable is missing or invalid
    """
    errors = []

    # NAME_APP is required in all environments
    name_app = os.getenv("NAME_APP", "").strip()
    if not name_app:
        errors.append("NAME_APP is required but missing or empty")

    # RUN_ENVIRONMENT is required in all environments
    run_env = os.getenv("RUN_ENVIRONMENT", "").strip().lower()
    valid_envs = ["development", "testing", "production"]
    if not run_env:
        errors.append("RUN_ENVIRONMENT is required but missing or empty")
    elif run_env not in valid_envs:
        errors.append(f"RUN_ENVIRONMENT must be one of {valid_envs}, got: {run_env}")

    # PATH_TO_LOGS is required in testing and production
    if run_env in ["testing", "production"]:
        path_to_logs = os.getenv("PATH_TO_LOGS", "").strip()
        if not path_to_logs:
            errors.append(f"PATH_TO_LOGS is required in {run_env} environment but is missing")

    # If any errors, log them and exit
    if errors:
        for error in errors:
            # Use stderr directly since logger may not be configured yet
            print(f"FATAL ERROR: {error}", file=sys.stderr)
        sys.exit(1)


def _configure_logger():
    """
    Configure the Loguru logger based on RUN_ENVIRONMENT.

    This function is called automatically when get_logger() is first invoked.
    """
    global _logger_configured

    if _logger_configured:
        return

    # Validate environment variables first
    _validate_required_env_vars()

    # Remove default logger
    logger.remove()

    # Get configuration from environment
    run_env = os.getenv("RUN_ENVIRONMENT", "production").lower()
    name_app = os.getenv("NAME_APP", "app")
    path_to_logs = os.getenv("PATH_TO_LOGS", "./logs")
    log_max_size = os.getenv("LOG_MAX_SIZE", "5 MB")
    log_max_files = int(os.getenv("LOG_MAX_FILES", "5"))

    # Development: Terminal only, DEBUG level
    if run_env == "development":
        logger.add(
            sys.stderr,
            format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
            level="DEBUG",
            colorize=True,
            backtrace=True,
            diagnose=True,
            enqueue=False
        )

    # Testing: Terminal + File, INFO level
    elif run_env == "testing":
        # Terminal output
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
            level="INFO",
            colorize=True,
            backtrace=True,
            diagnose=True,
            enqueue=False
        )

        # File output with rotation
        log_dir = Path(path_to_logs)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{name_app}.log"

        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level="INFO",
            rotation=log_max_size,
            retention=log_max_files,
            backtrace=True,
            diagnose=True,
            enqueue=True  # Process-safe
        )

    # Production: File only, INFO level
    elif run_env == "production":
        log_dir = Path(path_to_logs)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{name_app}.log"

        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level="INFO",
            rotation=log_max_size,
            retention=log_max_files,
            backtrace=True,
            diagnose=True,
            enqueue=True  # Process-safe
        )

    _logger_configured = True


def install_exception_handler():
    """
    Install global exception handler to catch and log uncaught exceptions.

    This ensures that crashes are always logged before exit, preventing
    silent failures in production environments.

    Should be called early in main.py startup.
    """
    def exception_handler(exc_type, exc_value, exc_traceback):
        # Preserve KeyboardInterrupt (Ctrl+C)
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # Log all other uncaught exceptions
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(
            "Uncaught exception - application terminating"
        )

    sys.excepthook = exception_handler


def get_logger(name: str = None):
    """
    Returns a configured Loguru logger instance.

    Args:
        name: Optional logger name (not used in Loguru, but maintained for API compatibility)

    Returns:
        loguru.Logger: Configured logger instance
    """
    # Ensure logger is configured on first call
    if not _logger_configured:
        _configure_logger()

    return logger


def log_early_exit(reason: str, exit_code: int = 0):
    """
    Log an early exit event and ensure logs are flushed.

    Use this when the service exits early due to guardrails, config failures,
    or other reasons. Ensures the exit reason is recorded in logs.

    Args:
        reason: Human-readable explanation of why the service is exiting
        exit_code: Exit code (0 for normal, non-zero for errors)
    """
    logger = get_logger()

    if exit_code == 0:
        logger.info(f"Early exit: {reason}")
    else:
        logger.error(f"Early exit with error: {reason}")

    # Flush all handlers to ensure logs are written
    logger.complete()
