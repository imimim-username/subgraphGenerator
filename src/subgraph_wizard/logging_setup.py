"""Logging configuration and setup."""

import logging
import os
from typing import Dict, Any


def _sanitize_env_for_logging() -> Dict[str, Any]:
    """
    Return a sanitized copy of environment variables, removing any keys
    that contain 'KEY' or 'TOKEN' to prevent accidental logging of secrets.
    """
    env_copy = {}
    for key, value in os.environ.items():
        key_upper = key.upper()
        if "KEY" not in key_upper and "TOKEN" not in key_upper:
            env_copy[key] = value
        else:
            env_copy[key] = "<REDACTED>"
    return env_copy


def setup_logging(level: str = None) -> logging.Logger:
    """
    Set up logging configuration.
    
    Reads LOG_LEVEL from environment (defaults to INFO).
    Configures a console handler with a standard format.
    Avoids logging any environment variable whose name contains 'KEY' or 'TOKEN'.
    
    Args:
        level: Optional log level string (e.g., 'INFO', 'DEBUG'). If None, reads from LOG_LEVEL env var.
    
    Returns:
        Configured logger instance for 'subgraph_wizard'.
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")
    
    # Convert level string to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure basic logging with console handler
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
        force=True  # Force reconfiguration if already configured
    )
    
    logger = logging.getLogger("subgraph_wizard")
    # Explicitly set the logger level to ensure it's not NOTSET
    logger.setLevel(log_level)
    
    # Log startup info (but sanitize environment)
    if logger.isEnabledFor(logging.DEBUG):
        sanitized_env = _sanitize_env_for_logging()
        logger.debug(f"Environment variables (sanitized): {sanitized_env}")
    
    return logger
