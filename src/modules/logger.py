"""
Unified logging module for NewsNexusDeduper02.
Provides environment-aware logging with automatic formatting.
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_logger(name: str = None):
    """
    Returns a configured logger instance.
    - In workstation mode: simple, readable logs
    - In server mode: prefixed logs with [NAME_APP]

    Args:
        name: Optional logger name. Defaults to NAME_APP from environment.

    Returns:
        logging.Logger: Configured logger instance
    """
    run_env = os.getenv("RUN_ENVIRONMENT", "production").lower()
    app_name = os.getenv("NAME_APP", "NewsNexusDeduper02")

    logger = logging.getLogger(name or app_name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()

    if run_env == "workstation":
        # Simple logs for local development
        formatter = logging.Formatter("%(levelname)s: %(message)s")
    else:
        # Structured logs for PM2 and server
        formatter = logging.Formatter(f"[{app_name}] %(message)s")

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
