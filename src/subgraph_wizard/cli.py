"""Command-line interface for Subgraph Wizard."""

import logging
import argparse
from pathlib import Path

from subgraph_wizard.config.io import load_config
from subgraph_wizard.config.validation import validate_config

logger = logging.getLogger(__name__)


def parse_args(argv):
    """
    Parse command-line arguments.
    
    Args:
        argv: List of command-line arguments (typically sys.argv[1:]).
    
    Returns:
        argparse.Namespace with parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Subgraph Wizard - Generate subgraph projects for The Graph"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to subgraph-config.json file"
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate subgraph from config"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be generated without writing files"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit"
    )
    
    return parser.parse_args(argv)


def run_from_args(args):
    """
    Run the CLI based on parsed arguments.
    
    Args:
        args: Parsed arguments from parse_args().
    
    Raises:
        SubgraphWizardError: For known error conditions.
    """
    if args.version:
        from subgraph_wizard import __version__
        print(f"subgraph-wizard version {__version__}")
        return
    
    # Determine and log the requested mode
    mode_parts = []
    if args.config:
        mode_parts.append(f"config={args.config}")
    if args.generate:
        mode_parts.append("generate")
    if args.dry_run:
        mode_parts.append("dry-run")
    
    if mode_parts:
        logger.info(f"CLI mode: {' '.join(mode_parts)}")
    else:
        logger.info("CLI mode: interactive wizard (no flags provided)")
    
    # If --config is provided, load and validate the configuration
    config = None
    if args.config:
        config_path = Path(args.config)
        logger.info(f"Loading configuration from: {config_path}")
        
        config = load_config(config_path)
        logger.info(f"Configuration loaded: {config.name}")
        
        validate_config(config)
        logger.info(f"Configuration validated successfully: {config.name}")
        logger.info(f"  Network: {config.network}")
        logger.info(f"  Contracts: {len(config.contracts)}")
        logger.info(f"  Mapping mode: {config.mappings_mode}")
        logger.info(f"  Complexity: {config.complexity}")
    
    # Handle generation
    if args.generate:
        if config is None:
            logger.warning("--generate requires --config. Please provide a configuration file.")
            return
        logger.info("Generation functionality will be implemented in a future milestone.")
    else:
        if not args.config:
            logger.info("Interactive wizard will be implemented in a future milestone.")


if __name__ == "__main__":
    run_from_args(parse_args([]))
