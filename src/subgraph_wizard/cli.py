"""Command-line interface for Subgraph Wizard."""

import argparse
import logging

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
        description="Subgraph Wizard — visual subgraph builder for The Graph"
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Start the visual node editor in your browser (default behaviour)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5173,
        help="Port to run the local server on (default: 5173)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the server but do not open the browser automatically",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    return parser.parse_args(argv)


def run_from_args(args):
    """
    Run the appropriate action based on parsed arguments.

    Args:
        args: Parsed arguments from parse_args().
    """
    if args.version:
        from subgraph_wizard import __version__
        print(f"subgraph-wizard version {__version__}")
        return

    # Default action (with or without --ui flag) is to start the local server
    logger.info(f"Starting visual editor on port {args.port}")
    from subgraph_wizard.server import start_server
    start_server(port=args.port, open_browser=not args.no_browser)
