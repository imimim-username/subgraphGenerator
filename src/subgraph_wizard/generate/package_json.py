"""Generate package.json file.

This module generates a package.json file for the subgraph project
with the necessary dependencies and scripts for building and deploying.
"""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig
from subgraph_wizard.utils.templating import render_template

logger = logging.getLogger(__name__)

# Default versions for The Graph dependencies
# These are the latest stable versions as of development time
DEFAULT_GRAPH_CLI_VERSION = "0.71.0"
DEFAULT_GRAPH_TS_VERSION = "0.32.0"


def render_package_json(
    config: SubgraphConfig,
    graph_cli_version: str | None = None,
    graph_ts_version: str | None = None,
) -> str:
    """Render a package.json file for the subgraph project.
    
    Generates a package.json with:
    - Project name and description based on config
    - Scripts for codegen, build, and deploy
    - Required dependencies (@graphprotocol/graph-cli and @graphprotocol/graph-ts)
    
    Args:
        config: Subgraph configuration.
        graph_cli_version: Optional version for @graphprotocol/graph-cli.
            Defaults to DEFAULT_GRAPH_CLI_VERSION.
        graph_ts_version: Optional version for @graphprotocol/graph-ts.
            Defaults to DEFAULT_GRAPH_TS_VERSION.
    
    Returns:
        Rendered package.json content as a string.
    """
    logger.info(f"Rendering package.json for: {config.name}")
    
    context: dict[str, Any] = {
        "name": _sanitize_package_name(config.name),
        "network": config.network,
        "graph_cli_version": graph_cli_version or DEFAULT_GRAPH_CLI_VERSION,
        "graph_ts_version": graph_ts_version or DEFAULT_GRAPH_TS_VERSION,
    }
    
    return render_template("package.json.j2", context)


def _sanitize_package_name(name: str) -> str:
    """Sanitize a name for use as an npm package name.
    
    npm package names must:
    - Be lowercase
    - Contain only URL-safe characters (letters, digits, hyphens, underscores)
    - Not start with a dot or underscore
    
    Args:
        name: Original project name.
    
    Returns:
        Sanitized package name.
    """
    # Convert to lowercase
    sanitized = name.lower()
    
    # Replace spaces and common separators with hyphens
    sanitized = sanitized.replace(" ", "-")
    sanitized = sanitized.replace("_", "-")
    
    # Remove any characters that aren't allowed
    allowed_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    sanitized = "".join(c for c in sanitized if c in allowed_chars)
    
    # Remove leading dots, underscores, or hyphens
    sanitized = sanitized.lstrip(".-_")
    
    # Ensure the name is not empty
    if not sanitized:
        sanitized = "subgraph"
    
    return sanitized
