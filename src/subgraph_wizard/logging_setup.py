"""Logging configuration and setup."""

import logging
import os

logger = logging.getLogger(__name__)


def setup_logging(level: str = None) -> logging.Logger:
    """Set up logging configuration."""
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")
    
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    return logging.getLogger("subgraph_wizard")
