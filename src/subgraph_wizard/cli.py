"""Command-line interface for Subgraph Wizard."""

import logging
import argparse

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
    
    # For now, log that generation is not yet implemented
    if args.generate:
        logger.info("Generation functionality will be implemented in a future milestone.")
    else:
        logger.info("Interactive wizard will be implemented in a future milestone.")


if __name__ == "__main__":
    run_from_args(parse_args([]))
