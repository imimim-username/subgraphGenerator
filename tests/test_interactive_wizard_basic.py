"""Tests for the interactive wizard (basic complexity).

These tests use monkeypatch to simulate user input and validate
that the wizard correctly builds SubgraphConfig and writes files.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from subgraph_wizard.interactive_wizard import (
    run_wizard,
    _validate_contract_address,
    _validate_contract_name,
    _validate_subgraph_name,
    _collect_contract,
    _get_abi_for_contract,
)
from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.errors import ValidationError, AbiFetchError


# Sample ABI for testing
SAMPLE_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]


class TestValidators:
    """Tests for validation helper functions."""
    
    def test_validate_contract_address_valid(self):
        """Valid Ethereum addresses should pass."""
        assert _validate_contract_address("0x1234567890123456789012345678901234567890")
        assert _validate_contract_address("0xABCDEF0123456789ABCDEF0123456789ABCDEF01")
        assert _validate_contract_address("0xabcdef0123456789abcdef0123456789abcdef01")
    
    def test_validate_contract_address_invalid(self):
        """Invalid addresses should fail."""
        assert not _validate_contract_address("")
        assert not _validate_contract_address("0x123")  # Too short
        assert not _validate_contract_address("1234567890123456789012345678901234567890")  # No 0x
        assert not _validate_contract_address("0xGHIJ567890123456789012345678901234567890")  # Invalid hex
        assert not _validate_contract_address("0x12345678901234567890123456789012345678901")  # Too long
    
    def test_validate_contract_name_valid(self):
        """Valid contract names should pass."""
        assert _validate_contract_name("MyToken")
        assert _validate_contract_name("Token123")
        assert _validate_contract_name("My_Token")
        assert _validate_contract_name("a")
    
    def test_validate_contract_name_invalid(self):
        """Invalid contract names should fail."""
        assert not _validate_contract_name("")
        assert not _validate_contract_name("123Token")  # Starts with number
        assert not _validate_contract_name("My-Token")  # Has hyphen
        assert not _validate_contract_name("_Token")  # Starts with underscore
        assert not _validate_contract_name("My Token")  # Has space
    
    def test_validate_subgraph_name_valid(self):
        """Valid subgraph names should pass."""
        assert _validate_subgraph_name("my-token")
        assert _validate_subgraph_name("token123")
        assert _validate_subgraph_name("mytoken")
        assert _validate_subgraph_name("a")
    
    def test_validate_subgraph_name_invalid(self):
        """Invalid subgraph names should fail."""
        assert not _validate_subgraph_name("")
        assert not _validate_subgraph_name("MyToken")  # Uppercase
        assert not _validate_subgraph_name("my_token")  # Underscore
        assert not _validate_subgraph_name("123token")  # Starts with number
        assert not _validate_subgraph_name("-token")  # Starts with hyphen


class TestRunWizard:
    """Tests for the main run_wizard function."""
    
    def test_run_wizard_basic_flow(self, tmp_path, monkeypatch):
        """Test wizard with basic inputs produces valid config."""
        output_dir = tmp_path / "test-subgraph"
        
        # Simulate user inputs
        inputs = iter([
            "test-subgraph",           # Subgraph name
            "1",                       # Network choice (arbitrum - alphabetically first)
            str(output_dir),           # Output directory
            "1",                       # Complexity choice (basic)
            "1",                       # Mapping mode (auto)
            "TestToken",               # Contract name
            "0x1234567890123456789012345678901234567890",  # Contract address
            "12345678",                # Start block
            "2",                       # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),    # Pasted ABI
            "END",                     # End paste marker
            "n",                       # Don't add another contract
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        config = run_wizard()
        
        # Verify config
        assert config.name == "test-subgraph"
        assert config.network == "arbitrum"
        assert config.output_dir == str(output_dir)
        assert config.mappings_mode == "auto"
        assert config.complexity == "basic"
        assert len(config.contracts) == 1
        
        contract = config.contracts[0]
        assert contract.name == "TestToken"
        assert contract.address == "0x1234567890123456789012345678901234567890"
        assert contract.start_block == 12345678
        assert contract.abi_path == "TestToken.json"
        
        # Verify files were created
        assert (output_dir / "subgraph-config.json").exists()
        assert (output_dir / "abis" / "TestToken.json").exists()
        
        # Verify config file content
        with open(output_dir / "subgraph-config.json") as f:
            saved_config = json.load(f)
        assert saved_config["name"] == "test-subgraph"
        assert saved_config["network"] == "arbitrum"
        
        # Verify ABI file content
        with open(output_dir / "abis" / "TestToken.json") as f:
            saved_abi = json.load(f)
        assert saved_abi == SAMPLE_ABI
    
    def test_run_wizard_stub_mode_warning(self, tmp_path, monkeypatch, capsys):
        """Test that selecting stub mode shows warning."""
        output_dir = tmp_path / "test-subgraph"
        
        # Simulate user inputs with stub mode selection
        inputs = iter([
            "test-subgraph",           # Subgraph name
            "1",                       # Network choice
            str(output_dir),           # Output directory
            "1",                       # Complexity choice (basic)
            "2",                       # Mapping mode (stub)
            "TestToken",               # Contract name
            "0x1234567890123456789012345678901234567890",  # Contract address
            "0",                       # Start block
            "2",                       # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),    # Pasted ABI
            "END",                     # End paste marker
            "n",                       # Don't add another contract
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        config = run_wizard()
        
        # Verify stub mode was selected
        assert config.mappings_mode == "stub"
        
        # Verify warning was printed
        captured = capsys.readouterr()
        assert "Stub mappings will be generated in a future milestone" in captured.out
    
    def test_run_wizard_multiple_contracts(self, tmp_path, monkeypatch):
        """Test wizard with multiple contracts."""
        output_dir = tmp_path / "multi-contract"
        
        # Simulate user inputs for two contracts
        inputs = iter([
            "multi-contract",          # Subgraph name
            "2",                       # Network choice (ethereum)
            str(output_dir),           # Output directory
            "1",                       # Complexity choice (basic)
            "1",                       # Mapping mode (auto)
            # First contract
            "TokenA",                  # Contract name
            "0x1111111111111111111111111111111111111111",  # Contract address
            "1000",                    # Start block
            "2",                       # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),    # Pasted ABI
            "END",                     # End paste marker
            "y",                       # Add another contract
            # Second contract
            "TokenB",                  # Contract name
            "0x2222222222222222222222222222222222222222",  # Contract address
            "2000",                    # Start block
            "2",                       # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),    # Pasted ABI
            "END",                     # End paste marker
            "n",                       # Don't add another contract
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        config = run_wizard()
        
        # Verify both contracts
        assert len(config.contracts) == 2
        assert config.contracts[0].name == "TokenA"
        assert config.contracts[1].name == "TokenB"
        
        # Verify both ABI files exist
        assert (output_dir / "abis" / "TokenA.json").exists()
        assert (output_dir / "abis" / "TokenB.json").exists()
    
    def test_run_wizard_duplicate_name_rejected(self, tmp_path, monkeypatch):
        """Test that duplicate contract names are rejected."""
        output_dir = tmp_path / "test-subgraph"
        
        # Simulate user trying to add duplicate name, then correcting
        inputs = iter([
            "test-subgraph",           # Subgraph name
            "1",                       # Network choice
            str(output_dir),           # Output directory
            "1",                       # Complexity choice (basic)
            "1",                       # Mapping mode (auto)
            # First contract
            "Token",                   # Contract name
            "0x1111111111111111111111111111111111111111",  # Contract address
            "0",                       # Start block
            "2",                       # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),    # Pasted ABI
            "END",                     # End paste marker
            "y",                       # Add another contract
            # Second contract (duplicate name)
            "Token",                   # Duplicate name - should be rejected
            "TokenB",                  # Corrected name
            "0x2222222222222222222222222222222222222222",  # Contract address
            "0",                       # Start block
            "2",                       # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),    # Pasted ABI
            "END",                     # End paste marker
            "n",                       # Don't add another contract
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        config = run_wizard()
        
        # Verify contracts have different names
        names = [c.name for c in config.contracts]
        assert len(names) == len(set(names))
        assert "Token" in names
        assert "TokenB" in names


class TestAbiAcquisition:
    """Tests for ABI acquisition methods in the wizard."""
    
    def test_get_abi_from_local_file(self, tmp_path, monkeypatch):
        """Test loading ABI from local file."""
        # Create a temporary ABI file
        abi_file = tmp_path / "test.json"
        abi_file.write_text(json.dumps(SAMPLE_ABI))
        
        # Simulate selecting local file and providing path
        inputs = iter([
            "1",                       # ABI source (local file)
            str(abi_file),             # File path
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        abi = _get_abi_for_contract("TestContract", "ethereum", "0x1234567890123456789012345678901234567890")
        
        assert abi == SAMPLE_ABI
    
    @patch("subgraph_wizard.interactive_wizard.fetch_abi_from_explorer")
    def test_get_abi_from_explorer(self, mock_fetch, monkeypatch):
        """Test fetching ABI from explorer."""
        mock_fetch.return_value = SAMPLE_ABI
        
        # Simulate selecting explorer fetch
        inputs = iter([
            "3",                       # ABI source (fetch from explorer)
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        abi = _get_abi_for_contract(
            "TestContract",
            "ethereum",
            "0x1234567890123456789012345678901234567890"
        )
        
        assert abi == SAMPLE_ABI
        mock_fetch.assert_called_once_with("ethereum", "0x1234567890123456789012345678901234567890")


class TestPromptUtils:
    """Tests for prompt utility functions."""
    
    def test_ask_string_with_default(self, monkeypatch):
        """Test ask_string returns default on empty input."""
        from subgraph_wizard.utils.prompts_utils import ask_string
        
        monkeypatch.setattr("builtins.input", lambda x: "")
        
        result = ask_string("Test prompt", default="default_value")
        assert result == "default_value"
    
    def test_ask_string_with_value(self, monkeypatch):
        """Test ask_string returns user input."""
        from subgraph_wizard.utils.prompts_utils import ask_string
        
        monkeypatch.setattr("builtins.input", lambda x: "user_value")
        
        result = ask_string("Test prompt", default="default_value")
        assert result == "user_value"
    
    def test_ask_choice_returns_selection(self, monkeypatch):
        """Test ask_choice returns selected option."""
        from subgraph_wizard.utils.prompts_utils import ask_choice
        
        monkeypatch.setattr("builtins.input", lambda x: "2")
        
        result = ask_choice("Select", ["option1", "option2", "option3"])
        assert result == "option2"
    
    def test_ask_choice_default(self, monkeypatch):
        """Test ask_choice returns default on empty input."""
        from subgraph_wizard.utils.prompts_utils import ask_choice
        
        monkeypatch.setattr("builtins.input", lambda x: "")
        
        result = ask_choice("Select", ["option1", "option2", "option3"], default_index=1)
        assert result == "option2"
    
    def test_ask_yes_no_yes(self, monkeypatch):
        """Test ask_yes_no returns True for yes."""
        from subgraph_wizard.utils.prompts_utils import ask_yes_no
        
        monkeypatch.setattr("builtins.input", lambda x: "y")
        assert ask_yes_no("Continue?") is True
        
        monkeypatch.setattr("builtins.input", lambda x: "yes")
        assert ask_yes_no("Continue?") is True
    
    def test_ask_yes_no_no(self, monkeypatch):
        """Test ask_yes_no returns False for no."""
        from subgraph_wizard.utils.prompts_utils import ask_yes_no
        
        monkeypatch.setattr("builtins.input", lambda x: "n")
        assert ask_yes_no("Continue?") is False
        
        monkeypatch.setattr("builtins.input", lambda x: "no")
        assert ask_yes_no("Continue?") is False
    
    def test_ask_yes_no_default_true(self, monkeypatch):
        """Test ask_yes_no returns default True on empty."""
        from subgraph_wizard.utils.prompts_utils import ask_yes_no
        
        monkeypatch.setattr("builtins.input", lambda x: "")
        assert ask_yes_no("Continue?", default=True) is True
    
    def test_ask_yes_no_default_false(self, monkeypatch):
        """Test ask_yes_no returns default False on empty."""
        from subgraph_wizard.utils.prompts_utils import ask_yes_no
        
        monkeypatch.setattr("builtins.input", lambda x: "")
        assert ask_yes_no("Continue?", default=False) is False
    
    def test_ask_int_valid(self, monkeypatch):
        """Test ask_int returns parsed integer."""
        from subgraph_wizard.utils.prompts_utils import ask_int
        
        monkeypatch.setattr("builtins.input", lambda x: "42")
        
        result = ask_int("Enter number")
        assert result == 42
    
    def test_ask_int_default(self, monkeypatch):
        """Test ask_int returns default on empty."""
        from subgraph_wizard.utils.prompts_utils import ask_int
        
        monkeypatch.setattr("builtins.input", lambda x: "")
        
        result = ask_int("Enter number", default=100)
        assert result == 100
