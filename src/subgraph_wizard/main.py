"""Main entry point for the Subgraph Wizard CLI."""

import logging
import os
import sys
import traceback

from dotenv import load_dotenv

from subgraph_wizard.logging_setup import setup_logging
from subgraph_wizard.cli import parse_args, run_from_args
from subgraph_wizard.errors import SubgraphWizardError


def run():
    """
    Main entry point for the subgraph-wizard command.

    Sets up logging, parses CLI arguments, and starts the visual editor server.
    Handles SubgraphWizardError exceptions with user-friendly messages.
    Shows full traceback only if DEBUG environment variable is set.
    """
    # Load .env from the current working directory (where the user runs the
    # command) so API keys and other settings are available without requiring
    # manual `export` calls.  Variables already set in the environment take
    # precedence (override=False is the default).
    load_dotenv()

    logger = setup_logging()
    logger.info("Subgraph Wizard starting...")

    try:
        args = parse_args(sys.argv[1:])
        run_from_args(args)
    except SubgraphWizardError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
    except Exception as e:
        if os.getenv("DEBUG", "").lower() in ("1", "true", "yes"):
            logger.exception("Unexpected error occurred:")
            traceback.print_exc()
        else:
            logger.error(f"Unexpected error: {e}")
            logger.info("Set DEBUG=1 environment variable to see full traceback.")
        sys.exit(1)


if __name__ == "__main__":
    run()
