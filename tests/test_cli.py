"""Tests for CLI argument parsing and execution."""

import logging
import os
import sys
import pytest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from subgraph_wizard.cli import parse_args, run_from_args
from subgraph_wizard.errors import SubgraphWizardError, ValidationError
from subgraph_wizard.logging_setup import setup_logging


class TestParseArgs:
    """Test CLI argument parsing."""

    def test_parse_args_no_flags(self):
        """No flags — defaults are set correctly."""
        args = parse_args([])
        assert args.ui is False
        assert args.port == 5173
        assert args.no_browser is False
        assert args.version is False

    def test_parse_args_ui_flag(self):
        """--ui flag is recognised."""
        args = parse_args(["--ui"])
        assert args.ui is True

    def test_parse_args_port(self):
        """--port overrides the default."""
        args = parse_args(["--port", "8080"])
        assert args.port == 8080

    def test_parse_args_no_browser(self):
        """--no-browser flag is recognised."""
        args = parse_args(["--no-browser"])
        assert args.no_browser is True

    def test_parse_args_version_flag(self):
        """--version flag is recognised."""
        args = parse_args(["--version"])
        assert args.version is True

    def test_parse_args_ui_with_port(self):
        """--ui and --port can be combined."""
        args = parse_args(["--ui", "--port", "9000"])
        assert args.ui is True
        assert args.port == 9000


class TestRunFromArgs:
    """Test CLI execution based on parsed arguments."""

    def test_version_flag_prints_version(self):
        """--version prints version string and returns without starting server."""
        args = Namespace(version=True, ui=False, port=5173, no_browser=False)
        with patch("builtins.print") as mock_print:
            run_from_args(args)
        mock_print.assert_called_once()
        assert "subgraph-wizard version" in mock_print.call_args[0][0]

    def test_version_flag_does_not_start_server(self):
        """--version must not call start_server."""
        args = Namespace(version=True, ui=False, port=5173, no_browser=False)
        with patch("subgraph_wizard.server.start_server") as mock_server:
            with patch("builtins.print"):
                run_from_args(args)
        mock_server.assert_not_called()

    def test_no_flags_starts_server(self):
        """Running with no flags starts the server (default behaviour)."""
        args = Namespace(version=False, ui=False, port=5173, no_browser=False)
        with patch("subgraph_wizard.server.start_server") as mock_server:
            run_from_args(args)
        mock_server.assert_called_once_with(port=5173, open_browser=True)

    def test_ui_flag_starts_server(self):
        """--ui flag starts the server."""
        args = Namespace(version=False, ui=True, port=5173, no_browser=False)
        with patch("subgraph_wizard.server.start_server") as mock_server:
            run_from_args(args)
        mock_server.assert_called_once_with(port=5173, open_browser=True)

    def test_custom_port_passed_to_server(self):
        """--port value is forwarded to start_server."""
        args = Namespace(version=False, ui=False, port=8888, no_browser=False)
        with patch("subgraph_wizard.server.start_server") as mock_server:
            run_from_args(args)
        mock_server.assert_called_once_with(port=8888, open_browser=True)

    def test_no_browser_disables_auto_open(self):
        """--no-browser passes open_browser=False to start_server."""
        args = Namespace(version=False, ui=False, port=5173, no_browser=True)
        with patch("subgraph_wizard.server.start_server") as mock_server:
            run_from_args(args)
        mock_server.assert_called_once_with(port=5173, open_browser=False)


class TestErrorHandling:
    """Test error handling in the main entry point."""

    def test_subgraph_wizard_error_exits_1(self):
        """SubgraphWizardError produces exit code 1 with a friendly message."""
        from subgraph_wizard.main import run

        with patch.object(sys, "argv", ["subgraph-wizard"]):
            with patch("subgraph_wizard.main.setup_logging") as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger

                with patch("subgraph_wizard.main.run_from_args") as mock_run:
                    mock_run.side_effect = SubgraphWizardError("Test error")

                    with pytest.raises(SystemExit) as exc:
                        run()

        assert exc.value.code == 1
        mock_logger.error.assert_called_once()
        assert "Test error" in mock_logger.error.call_args[0][0]

    def test_validation_error_exits_1(self):
        """ValidationError (subclass of SubgraphWizardError) exits with code 1."""
        from subgraph_wizard.main import run

        with patch.object(sys, "argv", ["subgraph-wizard"]):
            with patch("subgraph_wizard.main.setup_logging") as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger

                with patch("subgraph_wizard.main.run_from_args") as mock_run:
                    mock_run.side_effect = ValidationError("Validation failed")

                    with pytest.raises(SystemExit) as exc:
                        run()

        assert exc.value.code == 1

    def test_keyboard_interrupt_exits_cleanly(self):
        """Ctrl+C (KeyboardInterrupt) exits with code 0."""
        from subgraph_wizard.main import run

        with patch.object(sys, "argv", ["subgraph-wizard"]):
            with patch("subgraph_wizard.main.setup_logging") as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger

                with patch("subgraph_wizard.main.run_from_args") as mock_run:
                    mock_run.side_effect = KeyboardInterrupt()

                    with pytest.raises(SystemExit) as exc:
                        run()

        assert exc.value.code == 0

    def test_unexpected_error_without_debug(self):
        """Unexpected errors show a friendly message (no traceback) without DEBUG."""
        from subgraph_wizard.main import run

        with patch.object(sys, "argv", ["subgraph-wizard"]):
            with patch.dict(os.environ, {}, clear=True):
                with patch("subgraph_wizard.main.setup_logging") as mock_setup:
                    mock_logger = MagicMock()
                    mock_setup.return_value = mock_logger

                    with patch("subgraph_wizard.main.run_from_args") as mock_run:
                        mock_run.side_effect = RuntimeError("Something went wrong")

                        with pytest.raises(SystemExit) as exc:
                            run()

        assert exc.value.code == 1
        mock_logger.error.assert_called()
        mock_logger.info.assert_called()  # "Set DEBUG=1 ..." hint

    def test_unexpected_error_with_debug_shows_traceback(self):
        """Unexpected errors print full traceback when DEBUG=1."""
        from subgraph_wizard.main import run

        with patch.object(sys, "argv", ["subgraph-wizard"]):
            with patch.dict(os.environ, {"DEBUG": "1"}, clear=False):
                with patch("subgraph_wizard.main.setup_logging") as mock_setup:
                    mock_logger = MagicMock()
                    mock_setup.return_value = mock_logger

                    with patch("subgraph_wizard.main.run_from_args") as mock_run:
                        mock_run.side_effect = RuntimeError("Unexpected")

                        with patch("subgraph_wizard.main.traceback.print_exc") as mock_tb:
                            with pytest.raises(SystemExit) as exc:
                                run()

        assert exc.value.code == 1
        mock_logger.exception.assert_called()
        mock_tb.assert_called_once()


class TestLoggingSetup:
    """Test logging setup."""

    def test_default_level_is_info(self):
        """Logging defaults to INFO when LOG_LEVEL is not set."""
        with patch.dict(os.environ, {}, clear=True):
            logging.root.setLevel(logging.NOTSET)
            logger = setup_logging()
        assert logger.getEffectiveLevel() == logging.INFO

    def test_level_from_env(self):
        """LOG_LEVEL env var overrides the default."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=False):
            logging.root.setLevel(logging.NOTSET)
            logger = setup_logging()
        assert logger.getEffectiveLevel() == logging.DEBUG

    def test_explicit_level_argument(self):
        """setup_logging(level=...) sets the specified level."""
        logging.root.setLevel(logging.NOTSET)
        logger = setup_logging(level="WARNING")
        assert logger.getEffectiveLevel() == logging.WARNING
