"""Tests for subgraph.yaml generation."""

import pytest

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.generate.subgraph_yaml import render_subgraph_yaml


@pytest.fixture
def single_contract_config():
    """Create a config with a single contract."""
    return SubgraphConfig(
        name="test-subgraph",
        network="ethereum",
        output_dir="./test-output",
        mappings_mode="auto",
        contracts=[
            ContractConfig(
                name="TestToken",
                address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                start_block=12345678,
                abi_path="TestToken.json",
            )
        ],
    )


@pytest.fixture
def multi_contract_config():
    """Create a config with multiple contracts."""
    return SubgraphConfig(
        name="multi-contract-subgraph",
        network="optimism",
        output_dir="./multi-output",
        mappings_mode="auto",
        contracts=[
            ContractConfig(
                name="TokenA",
                address="0x1111111111111111111111111111111111111111",
                start_block=1000000,
                abi_path="TokenA.json",
            ),
            ContractConfig(
                name="TokenB",
                address="0x2222222222222222222222222222222222222222",
                start_block=2000000,
                abi_path="TokenB.json",
            ),
        ],
    )


class TestRenderSubgraphYaml:
    """Tests for render_subgraph_yaml function."""
    
    def test_contains_spec_version(self, single_contract_config):
        """Test that output contains specVersion."""
        result = render_subgraph_yaml(single_contract_config)
        assert "specVersion: 1.0.0" in result
    
    def test_contains_schema_file(self, single_contract_config):
        """Test that output contains schema file reference."""
        result = render_subgraph_yaml(single_contract_config)
        assert "file: ./schema.graphql" in result
    
    def test_contains_correct_network(self, single_contract_config):
        """Test that output contains correct network."""
        result = render_subgraph_yaml(single_contract_config)
        assert "network: ethereum" in result
    
    def test_contains_contract_name(self, single_contract_config):
        """Test that output contains contract name."""
        result = render_subgraph_yaml(single_contract_config)
        assert "name: TestToken" in result
    
    def test_contains_contract_address(self, single_contract_config):
        """Test that output contains contract address."""
        result = render_subgraph_yaml(single_contract_config)
        assert '0x6B175474E89094C44Da98b954EedeAC495271d0F' in result
    
    def test_contains_start_block(self, single_contract_config):
        """Test that output contains start block."""
        result = render_subgraph_yaml(single_contract_config)
        assert "startBlock: 12345678" in result
    
    def test_contains_abi_path(self, single_contract_config):
        """Test that output contains ABI path."""
        result = render_subgraph_yaml(single_contract_config)
        assert "TestToken.json" in result
    
    def test_contains_mapping_file_path(self, single_contract_config):
        """Test that output contains mapping file path."""
        result = render_subgraph_yaml(single_contract_config)
        assert "./src/mappings/TestToken.ts" in result
    
    def test_multi_contract_contains_both_names(self, multi_contract_config):
        """Test that multi-contract config includes all contract names."""
        result = render_subgraph_yaml(multi_contract_config)
        assert "name: TokenA" in result
        assert "name: TokenB" in result
    
    def test_multi_contract_contains_both_addresses(self, multi_contract_config):
        """Test that multi-contract config includes all addresses."""
        result = render_subgraph_yaml(multi_contract_config)
        assert "0x1111111111111111111111111111111111111111" in result
        assert "0x2222222222222222222222222222222222222222" in result
    
    def test_multi_contract_network(self, multi_contract_config):
        """Test that all data sources use the same network."""
        result = render_subgraph_yaml(multi_contract_config)
        # Count occurrences of network
        assert result.count("network: optimism") == 2
    
    def test_contains_event_handlers_section(self, single_contract_config):
        """Test that output contains eventHandlers section."""
        result = render_subgraph_yaml(single_contract_config)
        assert "eventHandlers:" in result
    
    def test_contains_entities_section(self, single_contract_config):
        """Test that output contains entities section."""
        result = render_subgraph_yaml(single_contract_config)
        assert "entities:" in result
    
    def test_valid_yaml_structure(self, single_contract_config):
        """Test that output is valid YAML structure."""
        result = render_subgraph_yaml(single_contract_config)
        
        # Basic structural checks
        assert result.startswith("specVersion:")
        assert "dataSources:" in result
        assert "kind: ethereum" in result
        assert "mapping:" in result

