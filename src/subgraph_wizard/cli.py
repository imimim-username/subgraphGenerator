"""Command-line interface for Subgraph Wizard."""

import logging
import argparse

logger = logging.getLogger(__name__)


def parse_args(argv):
    """Parse command-line arguments."""
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
    """Run the CLI based on parsed arguments."""
    if args.version:
        from subgraph_wizard import __version__
        print(f"subgraph-wizard version {__version__}")
        return
    
    logger.info(f"CLI mode requested. Config: {args.config}, Generate: {args.generate}, Dry-run: {args.dry_run}")
    logger.info("Not implemented yet.")


if __name__ == "__main__":
    run_from_args(parse_args([]))
