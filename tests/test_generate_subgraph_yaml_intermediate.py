"""Tests for subgraph.yaml generation with intermediate complexity.

This module tests the generation of subgraph.yaml with call handlers
and block handlers enabled.
"""

import pytest

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.generate.subgraph_yaml import render_subgraph_yaml


@pytest.fixture
def intermediate_config_with_call_handlers():
    """Create a config with intermediate complexity and call handlers."""
    return SubgraphConfig(
        name="intermediate-subgraph",
        network="ethereum",
        output_dir="./test-output",
        mappings_mode="auto",
        complexity="intermediate",
        config_version=2,
        contracts=[
            ContractConfig(
                name="TestToken",
                address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                start_block=12345678,
                abi_path="TestToken.json",
                call_handlers=["transfer(address,uint256)", "approve(address,uint256)"],
                block_handler=False,
            )
        ],
    )


@pytest.fixture
def intermediate_config_with_block_handler():
    """Create a config with intermediate complexity and block handler."""
    return SubgraphConfig(
        name="intermediate-subgraph",
        network="ethereum",
        output_dir="./test-output",
        mappings_mode="auto",
        complexity="intermediate",
        config_version=2,
        contracts=[
            ContractConfig(
                name="TestToken",
                address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                start_block=12345678,
                abi_path="TestToken.json",
                call_handlers=None,
                block_handler=True,
            )
        ],
    )


@pytest.fixture
def intermediate_config_with_both():
    """Create a config with intermediate complexity with call and block handlers."""
    return SubgraphConfig(
        name="intermediate-subgraph",
        network="ethereum",
        output_dir="./test-output",
        mappings_mode="auto",
        complexity="intermediate",
        config_version=2,
        contracts=[
            ContractConfig(
                name="TestToken",
                address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                start_block=12345678,
                abi_path="TestToken.json",
                call_handlers=["transfer(address,uint256)"],
                block_handler=True,
            )
        ],
    )


class TestIntermediateCallHandlers:
    """Tests for call handler generation."""
    
    def test_contains_call_handlers_section(self, intermediate_config_with_call_handlers):
        """Test that output contains callHandlers section."""
        result = render_subgraph_yaml(intermediate_config_with_call_handlers)
        assert "callHandlers:" in result
    
    def test_contains_transfer_call_handler(self, intermediate_config_with_call_handlers):
        """Test that output contains transfer call handler."""
        result = render_subgraph_yaml(intermediate_config_with_call_handlers)
        assert "transfer(address,uint256)" in result
        assert "handleTransferCall" in result
    
    def test_contains_approve_call_handler(self, intermediate_config_with_call_handlers):
        """Test that output contains approve call handler."""
        result = render_subgraph_yaml(intermediate_config_with_call_handlers)
        assert "approve(address,uint256)" in result
        assert "handleApproveCall" in result
    
    def test_contains_call_handler_entities(self, intermediate_config_with_call_handlers):
        """Test that entities include call handler entity types."""
        result = render_subgraph_yaml(intermediate_config_with_call_handlers)
        assert "TransferCall" in result
        assert "ApproveCall" in result


class TestIntermediateBlockHandler:
    """Tests for block handler generation."""
    
    def test_contains_block_handlers_section(self, intermediate_config_with_block_handler):
        """Test that output contains blockHandlers section."""
        result = render_subgraph_yaml(intermediate_config_with_block_handler)
        assert "blockHandlers:" in result
    
    def test_contains_block_handler_name(self, intermediate_config_with_block_handler):
        """Test that output contains correct block handler name."""
        result = render_subgraph_yaml(intermediate_config_with_block_handler)
        assert "handleTestTokenBlock" in result
    
    def test_contains_block_handler_entity(self, intermediate_config_with_block_handler):
        """Test that entities include block handler entity type."""
        result = render_subgraph_yaml(intermediate_config_with_block_handler)
        assert "TestTokenBlock" in result


class TestIntermediateBothHandlers:
    """Tests for configs with both call and block handlers."""
    
    def test_contains_both_handler_sections(self, intermediate_config_with_both):
        """Test that output contains both callHandlers and blockHandlers sections."""
        result = render_subgraph_yaml(intermediate_config_with_both)
        assert "callHandlers:" in result
        assert "blockHandlers:" in result
    
    def test_contains_all_handlers(self, intermediate_config_with_both):
        """Test that output contains all handler definitions."""
        result = render_subgraph_yaml(intermediate_config_with_both)
        # Call handler
        assert "handleTransferCall" in result
        # Block handler
        assert "handleTestTokenBlock" in result
    
    def test_valid_yaml_structure(self, intermediate_config_with_both):
        """Test that output is valid YAML structure."""
        result = render_subgraph_yaml(intermediate_config_with_both)
        
        # Basic structural checks
        assert result.startswith("specVersion:")
        assert "dataSources:" in result
        assert "kind: ethereum" in result
        assert "mapping:" in result


class TestBasicModeNoIntermediateFeatures:
    """Tests that basic mode doesn't include intermediate features."""
    
    @pytest.fixture
    def basic_config(self):
        """Create a basic complexity config."""
        return SubgraphConfig(
            name="basic-subgraph",
            network="ethereum",
            output_dir="./test-output",
            mappings_mode="auto",
            complexity="basic",
            config_version=1,
            contracts=[
                ContractConfig(
                    name="TestToken",
                    address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                    start_block=12345678,
                    abi_path="TestToken.json",
                )
            ],
        )
    
    def test_no_call_handlers_section(self, basic_config):
        """Test that basic mode doesn't include callHandlers section."""
        result = render_subgraph_yaml(basic_config)
        assert "callHandlers:" not in result
    
    def test_no_block_handlers_section(self, basic_config):
        """Test that basic mode doesn't include blockHandlers section."""
        result = render_subgraph_yaml(basic_config)
        assert "blockHandlers:" not in result


class TestIntermediateValidation:
    """Tests for intermediate complexity validation."""
    
    def test_intermediate_config_version_is_2(self, intermediate_config_with_call_handlers):
        """Test that intermediate configs have version 2."""
        assert intermediate_config_with_call_handlers.config_version == 2
    
    def test_intermediate_complexity_is_set(self, intermediate_config_with_call_handlers):
        """Test that complexity is set to intermediate."""
        assert intermediate_config_with_call_handlers.complexity == "intermediate"
    
    def test_call_handlers_list_not_empty(self, intermediate_config_with_call_handlers):
        """Test that call_handlers list is populated."""
        contract = intermediate_config_with_call_handlers.contracts[0]
        assert contract.call_handlers is not None
        assert len(contract.call_handlers) == 2


class TestMultiContractIntermediate:
    """Tests for intermediate complexity with multiple contracts."""
    
    @pytest.fixture
    def multi_contract_intermediate_config(self):
        """Create an intermediate config with multiple contracts."""
        return SubgraphConfig(
            name="multi-intermediate",
            network="ethereum",
            output_dir="./test-output",
            mappings_mode="auto",
            complexity="intermediate",
            config_version=2,
            contracts=[
                ContractConfig(
                    name="TokenA",
                    address="0x1111111111111111111111111111111111111111",
                    start_block=1000000,
                    abi_path="TokenA.json",
                    call_handlers=["transfer(address,uint256)"],
                    block_handler=False,
                ),
                ContractConfig(
                    name="TokenB",
                    address="0x2222222222222222222222222222222222222222",
                    start_block=2000000,
                    abi_path="TokenB.json",
                    call_handlers=None,
                    block_handler=True,
                ),
            ],
        )
    
    def test_first_contract_has_call_handlers(self, multi_contract_intermediate_config):
        """Test that first contract has call handlers in output."""
        result = render_subgraph_yaml(multi_contract_intermediate_config)
        # Should have call handler for TokenA
        assert "handleTransferCall" in result
    
    def test_second_contract_has_block_handler(self, multi_contract_intermediate_config):
        """Test that second contract has block handler in output."""
        result = render_subgraph_yaml(multi_contract_intermediate_config)
        # Should have block handler for TokenB
        assert "handleTokenBBlock" in result
