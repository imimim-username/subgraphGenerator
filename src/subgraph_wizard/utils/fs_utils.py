"""File system utility functions."""

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist.
    
    Args:
        path: Path to directory to create.
    
    Returns:
        The path to the created/existing directory.
    
    Raises:
        OSError: If directory cannot be created.
    """
    path = Path(path)
    if not path.exists():
        logger.debug(f"Creating directory: {path}")
        path.mkdir(parents=True, exist_ok=True)
    return path


def safe_write(path: Path, content: str) -> None:
    """Write content to file safely using temp file and rename.
    
    This function writes content to a temporary file first, then atomically
    renames it to the target path. This prevents partial writes if the process
    is interrupted.
    
    Args:
        path: Path to write the file to.
        content: Content to write.
    
    Raises:
        OSError: If file cannot be written.
    """
    path = Path(path)
    
    # Ensure parent directory exists
    ensure_dir(path.parent)
    
    # Create temp file in the same directory for atomic rename
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp"
    )
    
    try:
        # Write content to temp file
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Atomic rename (on POSIX systems)
        os.rename(temp_path, path)
        logger.debug(f"Wrote file: {path}")
        
    except Exception:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
