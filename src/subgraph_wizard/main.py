"""Main entry point for the Subgraph Wizard CLI."""

import logging
import sys

from subgraph_wizard.logging_setup import setup_logging
from subgraph_wizard.cli import parse_args, run_from_args


def run():
    """Main entry point for the subgraph-wizard command."""
    logger = setup_logging()
    logger.info("Subgraph Wizard starting...")
    
    try:
        args = parse_args(sys.argv[1:])
        run_from_args(args)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
