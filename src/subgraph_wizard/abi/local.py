"""Load ABI from local files.

This module provides functionality to load and validate ABI JSON from
local filesystem paths.
"""

import json
import logging
from pathlib import Path
from typing import Any

from subgraph_wizard.errors import ValidationError, AbiFetchError
from subgraph_wizard.abi.utils import validate_abi

logger = logging.getLogger(__name__)


def load_abi_from_file(path: Path | str) -> list[dict[str, Any]]:
    """Load an ABI from a local JSON file.
    
    Args:
        path: Path to the ABI JSON file.
    
    Returns:
        Parsed ABI as a list of dictionaries.
    
    Raises:
        AbiFetchError: If the file cannot be read.
        ValidationError: If the file content is not valid ABI JSON.
    """
    path = Path(path)
    
    if not path.exists():
        raise AbiFetchError(f"ABI file not found: {path}")
    
    if not path.is_file():
        raise AbiFetchError(f"Path is not a file: {path}")
    
    logger.info(f"Loading ABI from file: {path}")
    
    try:
        content = path.read_text(encoding="utf-8")
    except IOError as e:
        raise AbiFetchError(f"Failed to read ABI file: {e}")
    
    # Handle empty files
    if not content.strip():
        raise ValidationError(f"ABI file is empty: {path}")
    
    # Parse JSON
    try:
        abi = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in ABI file {path}: {e}")
    
    # Validate structure
    if not isinstance(abi, list):
        raise ValidationError(f"ABI must be a JSON array, got {type(abi).__name__}")
    
    # Validate ABI structure
    validate_abi(abi)
    
    logger.debug(f"Successfully loaded ABI with {len(abi)} entries from {path}")
    return abi


def write_abi_to_file(abi: list[dict[str, Any]], path: Path | str) -> None:
    """Write an ABI to a local JSON file.
    
    Args:
        abi: ABI data to write.
        path: Target file path.
    
    Raises:
        IOError: If the file cannot be written.
    """
    path = Path(path)
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    content = json.dumps(abi, indent=2)
    path.write_text(content, encoding="utf-8")
    
    logger.debug(f"Wrote ABI with {len(abi)} entries to {path}")
