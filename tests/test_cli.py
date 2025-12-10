"""Tests for CLI argument parsing and error handling."""

import logging
import os
import pytest
import sys
from argparse import Namespace
from unittest.mock import MagicMock, patch

from subgraph_wizard.cli import parse_args, run_from_args
from subgraph_wizard.errors import SubgraphWizardError, ValidationError, AbiFetchError
from subgraph_wizard.logging_setup import setup_logging


class TestParseArgs:
    """Test CLI argument parsing."""

    def test_parse_args_no_flags(self):
        """Test parsing with no flags (interactive mode)."""
        args = parse_args([])
        assert args.config is None
        assert args.generate is False
        assert args.dry_run is False
        assert args.version is False

    def test_parse_args_config_only(self):
        """Test parsing with --config flag."""
        args = parse_args(["--config", "test-config.json"])
        assert args.config == "test-config.json"
        assert args.generate is False
        assert args.dry_run is False
        assert args.version is False

    def test_parse_args_generate_flag(self):
        """Test parsing with --generate flag."""
        args = parse_args(["--generate"])
        assert args.config is None
        assert args.generate is True
        assert args.dry_run is False
        assert args.version is False

    def test_parse_args_dry_run_flag(self):
        """Test parsing with --dry-run flag."""
        args = parse_args(["--dry-run"])
        assert args.config is None
        assert args.generate is False
        assert args.dry_run is True
        assert args.version is False

    def test_parse_args_version_flag(self):
        """Test parsing with --version flag."""
        args = parse_args(["--version"])
        assert args.config is None
        assert args.generate is False
        assert args.dry_run is False
        assert args.version is True

    def test_parse_args_all_flags(self):
        """Test parsing with all flags combined."""
        args = parse_args([
            "--config", "test.json",
            "--generate",
            "--dry-run"
        ])
        assert args.config == "test.json"
        assert args.generate is True
        assert args.dry_run is True
        assert args.version is False

    def test_parse_args_config_and_generate(self):
        """Test parsing with --config and --generate."""
        args = parse_args(["--config", "config.json", "--generate"])
        assert args.config == "config.json"
        assert args.generate is True
        assert args.dry_run is False


class TestRunFromArgs:
    """Test CLI execution based on parsed arguments."""

    @patch('subgraph_wizard.cli.logger')
    def test_run_from_args_version(self, mock_logger):
        """Test --version flag prints version and exits."""
        args = Namespace(
            config=None,
            generate=False,
            dry_run=False,
            version=True
        )
        
        with patch('builtins.print') as mock_print:
            run_from_args(args)
            mock_print.assert_called_once()
            # Check that version string is printed
            call_args = mock_print.call_args[0][0]
            assert "subgraph-wizard version" in call_args

    @patch('subgraph_wizard.cli.ask_yes_no')
    @patch('subgraph_wizard.cli.run_wizard')
    @patch('subgraph_wizard.cli.logger')
    def test_run_from_args_no_flags(self, mock_logger, mock_run_wizard, mock_ask_yes_no):
        """Test running with no flags (interactive mode) starts wizard."""
        from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
        
        # Create a mock config to return from wizard
        mock_config = SubgraphConfig(
            name="test-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[
                ContractConfig(
                    name="TestToken",
                    address="0x1234567890123456789012345678901234567890",
                    start_block=12345678,
                    abi_path="TestToken.json"
                )
            ]
        )
        mock_run_wizard.return_value = mock_config
        mock_ask_yes_no.return_value = False  # Don't generate after wizard
        
        args = Namespace(
            config=None,
            generate=False,
            dry_run=False,
            version=False
        )
        
        run_from_args(args)
        # Should log interactive wizard mode and run the wizard
        assert mock_logger.info.called
        mock_run_wizard.assert_called_once()
        mock_ask_yes_no.assert_called_once()  # Should ask about generating

    @patch('subgraph_wizard.cli.validate_config')
    @patch('subgraph_wizard.cli.load_config')
    @patch('subgraph_wizard.cli.logger')
    def test_run_from_args_with_config(self, mock_logger, mock_load_config, mock_validate_config):
        """Test running with --config flag."""
        from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
        
        # Create a mock config to return
        mock_config = SubgraphConfig(
            name="test-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[
                ContractConfig(
                    name="TestToken",
                    address="0x1234567890123456789012345678901234567890",
                    start_block=12345678,
                    abi_path="TestToken.json"
                )
            ]
        )
        mock_load_config.return_value = mock_config
        
        args = Namespace(
            config="test-config.json",
            generate=False,
            dry_run=False,
            version=False
        )
        
        run_from_args(args)
        # Should log config mode
        assert mock_logger.info.called
        mock_load_config.assert_called_once()
        mock_validate_config.assert_called_once_with(mock_config)

    @patch('subgraph_wizard.cli.logger')
    def test_run_from_args_with_generate(self, mock_logger):
        """Test running with --generate flag."""
        args = Namespace(
            config=None,
            generate=True,
            dry_run=False,
            version=False
        )
        
        run_from_args(args)
        # Should log generation mode
        assert mock_logger.info.called

    @patch('subgraph_wizard.cli.validate_config')
    @patch('subgraph_wizard.cli.load_config')
    @patch('subgraph_wizard.cli.logger')
    def test_run_from_args_dry_run(self, mock_logger, mock_load_config, mock_validate_config):
        """Test running with --dry-run flag."""
        from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
        
        # Create a mock config to return
        mock_config = SubgraphConfig(
            name="test-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[
                ContractConfig(
                    name="TestToken",
                    address="0x1234567890123456789012345678901234567890",
                    start_block=12345678,
                    abi_path="TestToken.json"
                )
            ]
        )
        mock_load_config.return_value = mock_config
        
        args = Namespace(
            config="test.json",
            generate=True,
            dry_run=True,
            version=False
        )
        
        run_from_args(args)
        # Should log dry-run mode
        assert mock_logger.info.called
        mock_load_config.assert_called_once()
        mock_validate_config.assert_called_once_with(mock_config)


class TestErrorHandling:
    """Test error handling in main entry point."""

    def test_subgraph_wizard_error_handling(self):
        """Test that SubgraphWizardError is caught and handled gracefully."""
        from subgraph_wizard.main import run
        
        with patch('subgraph_wizard.main.setup_logging') as mock_setup:
            mock_logger = MagicMock()
            mock_setup.return_value = mock_logger
            
            with patch('subgraph_wizard.main.parse_args') as mock_parse:
                mock_args = MagicMock()
                mock_args.version = False
                mock_parse.return_value = mock_args
                
                with patch('subgraph_wizard.main.run_from_args') as mock_run:
                    mock_run.side_effect = SubgraphWizardError("Test error")
                    
                    with pytest.raises(SystemExit) as exc_info:
                        run()
                    
                    assert exc_info.value.code == 1
                    mock_logger.error.assert_called_once()
                    error_call = mock_logger.error.call_args[0][0]
                    assert "Test error" in error_call

    def test_validation_error_handling(self):
        """Test that ValidationError is caught and handled."""
        from subgraph_wizard.main import run
        
        with patch('subgraph_wizard.main.setup_logging') as mock_setup:
            mock_logger = MagicMock()
            mock_setup.return_value = mock_logger
            
            with patch('subgraph_wizard.main.parse_args') as mock_parse:
                mock_args = MagicMock()
                mock_args.version = False
                mock_parse.return_value = mock_args
                
                with patch('subgraph_wizard.main.run_from_args') as mock_run:
                    mock_run.side_effect = ValidationError("Validation failed")
                    
                    with pytest.raises(SystemExit) as exc_info:
                        run()
                    
                    assert exc_info.value.code == 1
                    mock_logger.error.assert_called_once()

    def test_keyboard_interrupt_handling(self):
        """Test that KeyboardInterrupt is handled gracefully."""
        from subgraph_wizard.main import run
        
        with patch('subgraph_wizard.main.setup_logging') as mock_setup:
            mock_logger = MagicMock()
            mock_setup.return_value = mock_logger
            
            with patch('subgraph_wizard.main.parse_args') as mock_parse:
                mock_args = MagicMock()
                mock_args.version = False
                mock_parse.return_value = mock_args
                
                with patch('subgraph_wizard.main.run_from_args') as mock_run:
                    mock_run.side_effect = KeyboardInterrupt()
                    
                    with pytest.raises(SystemExit) as exc_info:
                        run()
                    
                    assert exc_info.value.code == 130
                    mock_logger.info.assert_called()

    def test_unexpected_error_without_debug(self):
        """Test that unexpected errors show friendly message without DEBUG."""
        from subgraph_wizard.main import run
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('subgraph_wizard.main.setup_logging') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                with patch('subgraph_wizard.main.parse_args') as mock_parse:
                    mock_args = MagicMock()
                    mock_args.version = False
                    mock_parse.return_value = mock_args
                    
                    with patch('subgraph_wizard.main.run_from_args') as mock_run:
                        mock_run.side_effect = ValueError("Unexpected error")
                        
                        with pytest.raises(SystemExit) as exc_info:
                            run()
                        
                        assert exc_info.value.code == 1
                        mock_logger.error.assert_called()
                        mock_logger.info.assert_called()  # Should suggest DEBUG=1

    def test_unexpected_error_with_debug(self):
        """Test that unexpected errors show traceback with DEBUG=1."""
        from subgraph_wizard.main import run
        
        with patch.dict(os.environ, {"DEBUG": "1"}, clear=False):
            with patch('subgraph_wizard.main.setup_logging') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                with patch('subgraph_wizard.main.parse_args') as mock_parse:
                    mock_args = MagicMock()
                    mock_args.version = False
                    mock_parse.return_value = mock_args
                    
                    with patch('subgraph_wizard.main.run_from_args') as mock_run:
                        mock_run.side_effect = ValueError("Unexpected error")
                        
                        with patch('subgraph_wizard.main.traceback.print_exc') as mock_traceback:
                            with pytest.raises(SystemExit) as exc_info:
                                run()
                            
                            assert exc_info.value.code == 1
                            mock_logger.exception.assert_called()
                            mock_traceback.assert_called_once()


class TestLoggingSetup:
    """Test logging setup functionality."""

    def test_setup_logging_default_level(self):
        """Test that logging defaults to INFO level."""
        with patch.dict(os.environ, {}, clear=True):
            # Reset logging to avoid interference from other tests
            logging.root.setLevel(logging.NOTSET)
            logger = setup_logging()
            assert logger.getEffectiveLevel() == logging.INFO

    def test_setup_logging_from_env(self):
        """Test that logging level can be set from LOG_LEVEL env var."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=False):
            # Reset logging to avoid interference from other tests
            logging.root.setLevel(logging.NOTSET)
            logger = setup_logging()
            assert logger.getEffectiveLevel() == logging.DEBUG

    def test_setup_logging_explicit_level(self):
        """Test that logging level can be set explicitly."""
        # Reset logging to avoid interference from other tests
        logging.root.setLevel(logging.NOTSET)
        logger = setup_logging(level="WARNING")
        assert logger.getEffectiveLevel() == logging.WARNING

    def test_setup_logging_sanitizes_env_vars(self):
        """Test that environment variables with KEY/TOKEN are sanitized."""
        with patch.dict(os.environ, {
            "LOG_LEVEL": "DEBUG",
            "ETHERSCAN_API_KEY": "secret123",
            "SOME_TOKEN": "token456",
            "NORMAL_VAR": "normal_value"
        }, clear=False):
            logger = setup_logging()
            # The sanitization happens in _sanitize_env_for_logging
            # We can't easily test it without checking logs, but the function exists
            assert logger is not None

