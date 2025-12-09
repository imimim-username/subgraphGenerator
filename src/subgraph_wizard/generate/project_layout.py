"""Project layout and directory structure management."""

import logging
from pathlib import Path
from typing import TypedDict

from subgraph_wizard.config.model import SubgraphConfig
from subgraph_wizard.utils.fs_utils import ensure_dir

logger = logging.getLogger(__name__)


class ProjectPaths(TypedDict):
    """Dictionary containing all project paths."""
    root_dir: Path
    abis_dir: Path
    src_dir: Path
    mappings_dir: Path


def prepare_project_structure(config: SubgraphConfig) -> ProjectPaths:
    """Create the project directory structure for a subgraph.
    
    Creates the following structure under config.output_dir:
    
        <output_dir>/
        ├── abis/
        └── src/
            └── mappings/
    
    Args:
        config: Subgraph configuration containing output_dir.
    
    Returns:
        Dictionary with paths to:
            - root_dir: Root output directory
            - abis_dir: Directory for ABI JSON files
            - src_dir: Source directory
            - mappings_dir: Directory for mapping TypeScript files
    
    Raises:
        OSError: If directories cannot be created.
    """
    root_dir = Path(config.output_dir)
    
    # Define all directory paths
    abis_dir = root_dir / "abis"
    src_dir = root_dir / "src"
    mappings_dir = src_dir / "mappings"
    
    # Create all directories
    logger.info(f"Preparing project structure in: {root_dir}")
    
    ensure_dir(root_dir)
    ensure_dir(abis_dir)
    ensure_dir(src_dir)
    ensure_dir(mappings_dir)
    
    logger.debug(f"Created directory structure:")
    logger.debug(f"  root_dir: {root_dir}")
    logger.debug(f"  abis_dir: {abis_dir}")
    logger.debug(f"  src_dir: {src_dir}")
    logger.debug(f"  mappings_dir: {mappings_dir}")
    
    return ProjectPaths(
        root_dir=root_dir,
        abis_dir=abis_dir,
        src_dir=src_dir,
        mappings_dir=mappings_dir,
    )
