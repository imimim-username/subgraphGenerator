"""Tests for configuration file I/O operations."""

import json
import pytest
from pathlib import Path

from subgraph_wizard.config.model import ContractConfig, SubgraphConfig
from subgraph_wizard.config.io import load_config, save_config
from subgraph_wizard.errors import ValidationError


class TestContractConfig:
    """Tests for ContractConfig dataclass."""
    
    def test_contract_config_creation(self):
        """Test creating a ContractConfig with required fields."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=12345678,
            abi_path="TestToken.json"
        )
        
        assert contract.name == "TestToken"
        assert contract.address == "0x1234567890123456789012345678901234567890"
        assert contract.start_block == 12345678
        assert contract.abi_path == "TestToken.json"
        assert contract.index_events is True  # Default value
    
    def test_contract_config_to_dict(self):
        """Test converting ContractConfig to dictionary."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=12345678,
            abi_path="TestToken.json",
            index_events=False
        )
        
        data = contract.to_dict()
        
        assert data == {
            "name": "TestToken",
            "address": "0x1234567890123456789012345678901234567890",
            "start_block": 12345678,
            "abi_path": "TestToken.json",
            "index_events": False
        }
    
    def test_contract_config_from_dict(self):
        """Test creating ContractConfig from dictionary."""
        data = {
            "name": "TestToken",
            "address": "0x1234567890123456789012345678901234567890",
            "start_block": 12345678,
            "abi_path": "TestToken.json"
        }
        
        contract = ContractConfig.from_dict(data)
        
        assert contract.name == "TestToken"
        assert contract.address == "0x1234567890123456789012345678901234567890"
        assert contract.start_block == 12345678
        assert contract.abi_path == "TestToken.json"
        assert contract.index_events is True  # Default value
    
    def test_contract_config_from_dict_with_index_events(self):
        """Test creating ContractConfig with explicit index_events."""
        data = {
            "name": "TestToken",
            "address": "0x1234567890123456789012345678901234567890",
            "start_block": 12345678,
            "abi_path": "TestToken.json",
            "index_events": False
        }
        
        contract = ContractConfig.from_dict(data)
        
        assert contract.index_events is False


class TestSubgraphConfig:
    """Tests for SubgraphConfig dataclass."""
    
    def test_subgraph_config_creation(self):
        """Test creating a SubgraphConfig with required fields."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=12345678,
            abi_path="TestToken.json"
        )
        
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[contract]
        )
        
        assert config.name == "my-subgraph"
        assert config.network == "ethereum"
        assert config.output_dir == "./output"
        assert config.mappings_mode == "auto"
        assert len(config.contracts) == 1
        assert config.config_version == 1  # Default
        assert config.complexity == "basic"  # Default
    
    def test_subgraph_config_to_dict(self):
        """Test converting SubgraphConfig to dictionary."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=12345678,
            abi_path="TestToken.json"
        )
        
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[contract]
        )
        
        data = config.to_dict()
        
        assert data["name"] == "my-subgraph"
        assert data["network"] == "ethereum"
        assert data["output_dir"] == "./output"
        assert data["mappings_mode"] == "auto"
        assert data["config_version"] == 1
        assert data["complexity"] == "basic"
        assert len(data["contracts"]) == 1
    
    def test_subgraph_config_from_dict(self):
        """Test creating SubgraphConfig from dictionary."""
        data = {
            "name": "my-subgraph",
            "network": "ethereum",
            "output_dir": "./output",
            "mappings_mode": "auto",
            "config_version": 1,
            "complexity": "basic",
            "contracts": [
                {
                    "name": "TestToken",
                    "address": "0x1234567890123456789012345678901234567890",
                    "start_block": 12345678,
                    "abi_path": "TestToken.json"
                }
            ]
        }
        
        config = SubgraphConfig.from_dict(data)
        
        assert config.name == "my-subgraph"
        assert config.network == "ethereum"
        assert len(config.contracts) == 1
        assert config.contracts[0].name == "TestToken"


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_valid_config(self, tmp_path):
        """Test loading a valid configuration file."""
        config_data = {
            "name": "my-subgraph",
            "network": "ethereum",
            "output_dir": "./output",
            "mappings_mode": "auto",
            "config_version": 1,
            "complexity": "basic",
            "contracts": [
                {
                    "name": "TestToken",
                    "address": "0x1234567890123456789012345678901234567890",
                    "start_block": 12345678,
                    "abi_path": "TestToken.json"
                }
            ]
        }
        
        config_path = tmp_path / "subgraph-config.json"
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        
        config = load_config(config_path)
        
        assert config.name == "my-subgraph"
        assert config.network == "ethereum"
        assert len(config.contracts) == 1
    
    def test_load_config_file_not_found(self, tmp_path):
        """Test loading a non-existent config file raises ValidationError."""
        config_path = tmp_path / "nonexistent.json"
        
        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_load_config_invalid_json(self, tmp_path):
        """Test loading an invalid JSON file raises ValidationError."""
        config_path = tmp_path / "invalid.json"
        with open(config_path, "w") as f:
            f.write("{ invalid json }")
        
        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)
        
        assert "invalid json" in str(exc_info.value).lower()
    
    def test_load_config_missing_required_fields(self, tmp_path):
        """Test loading config with missing required fields raises ValidationError."""
        config_data = {
            "name": "my-subgraph",
            # Missing: network, output_dir, mappings_mode
        }
        
        config_path = tmp_path / "subgraph-config.json"
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        
        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)
        
        assert "missing required fields" in str(exc_info.value).lower()
    
    def test_load_config_missing_contract_fields(self, tmp_path):
        """Test loading config with contract missing required fields."""
        config_data = {
            "name": "my-subgraph",
            "network": "ethereum",
            "output_dir": "./output",
            "mappings_mode": "auto",
            "contracts": [
                {
                    "name": "TestToken",
                    # Missing: address, start_block, abi_path
                }
            ]
        }
        
        config_path = tmp_path / "subgraph-config.json"
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        
        with pytest.raises(ValidationError) as exc_info:
            load_config(config_path)
        
        assert "contract" in str(exc_info.value).lower()
        assert "missing" in str(exc_info.value).lower()
    
    def test_load_config_directory_path(self, tmp_path):
        """Test loading config from a directory path raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            load_config(tmp_path)
        
        assert "not a file" in str(exc_info.value).lower()


class TestSaveConfig:
    """Tests for save_config function."""
    
    def test_save_config(self, tmp_path):
        """Test saving a valid configuration."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=12345678,
            abi_path="TestToken.json"
        )
        
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[contract]
        )
        
        config_path = tmp_path / "subgraph-config.json"
        save_config(config, config_path)
        
        assert config_path.exists()
        
        with open(config_path, "r") as f:
            data = json.load(f)
        
        assert data["name"] == "my-subgraph"
        assert data["network"] == "ethereum"
        assert data["config_version"] == 1
    
    def test_save_config_creates_parent_dirs(self, tmp_path):
        """Test save_config creates parent directories if they don't exist."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=12345678,
            abi_path="TestToken.json"
        )
        
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[contract]
        )
        
        config_path = tmp_path / "nested" / "deep" / "subgraph-config.json"
        save_config(config, config_path)
        
        assert config_path.exists()


class TestRoundTrip:
    """Tests for round-trip save and load operations."""
    
    def test_round_trip_config(self, tmp_path):
        """Test that save → load produces equivalent config."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=12345678,
            abi_path="TestToken.json",
            index_events=True
        )
        
        original_config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[contract],
            config_version=1,
            complexity="basic"
        )
        
        config_path = tmp_path / "subgraph-config.json"
        save_config(original_config, config_path)
        loaded_config = load_config(config_path)
        
        # Compare all fields
        assert loaded_config.name == original_config.name
        assert loaded_config.network == original_config.network
        assert loaded_config.output_dir == original_config.output_dir
        assert loaded_config.mappings_mode == original_config.mappings_mode
        assert loaded_config.config_version == original_config.config_version
        assert loaded_config.complexity == original_config.complexity
        assert len(loaded_config.contracts) == len(original_config.contracts)
        
        # Compare contract fields
        orig_contract = original_config.contracts[0]
        loaded_contract = loaded_config.contracts[0]
        assert loaded_contract.name == orig_contract.name
        assert loaded_contract.address == orig_contract.address
        assert loaded_contract.start_block == orig_contract.start_block
        assert loaded_contract.abi_path == orig_contract.abi_path
        assert loaded_contract.index_events == orig_contract.index_events
    
    def test_round_trip_multiple_contracts(self, tmp_path):
        """Test round-trip with multiple contracts."""
        contracts = [
            ContractConfig(
                name="TokenA",
                address="0x1111111111111111111111111111111111111111",
                start_block=1000,
                abi_path="TokenA.json"
            ),
            ContractConfig(
                name="TokenB",
                address="0x2222222222222222222222222222222222222222",
                start_block=2000,
                abi_path="TokenB.json",
                index_events=False
            )
        ]
        
        original_config = SubgraphConfig(
            name="multi-token-subgraph",
            network="optimism",
            output_dir="./multi-output",
            mappings_mode="stub",
            contracts=contracts
        )
        
        config_path = tmp_path / "subgraph-config.json"
        save_config(original_config, config_path)
        loaded_config = load_config(config_path)
        
        assert len(loaded_config.contracts) == 2
        assert loaded_config.contracts[0].name == "TokenA"
        assert loaded_config.contracts[1].name == "TokenB"
        assert loaded_config.contracts[1].index_events is False

