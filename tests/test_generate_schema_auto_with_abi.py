"""Tests for schema generation with real ABIs."""

import pytest

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.generate.schema import render_schema, get_all_entities_for_contract


# Sample ABI with a Transfer event
TRANSFER_ABI = [
    {
        "type": "event",
        "name": "Transfer",
        "inputs": [
            {"name": "from", "type": "address", "indexed": True},
            {"name": "to", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
]

# Sample ABI with multiple events
MULTI_EVENT_ABI = [
    {
        "type": "event",
        "name": "Transfer",
        "inputs": [
            {"name": "from", "type": "address", "indexed": True},
            {"name": "to", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
    {
        "type": "event",
        "name": "Approval",
        "inputs": [
            {"name": "owner", "type": "address", "indexed": True},
            {"name": "spender", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
]

# Sample ABI with various parameter types
COMPLEX_EVENT_ABI = [
    {
        "type": "event",
        "name": "ComplexEvent",
        "inputs": [
            {"name": "id", "type": "uint256", "indexed": True},
            {"name": "sender", "type": "address", "indexed": False},
            {"name": "flag", "type": "bool", "indexed": False},
            {"name": "data", "type": "bytes32", "indexed": False},
            {"name": "message", "type": "string", "indexed": False},
        ],
    },
]


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample SubgraphConfig for testing."""
    return SubgraphConfig(
        name="test-subgraph",
        network="ethereum",
        output_dir=str(tmp_path / "generated"),
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
def multi_contract_config(tmp_path):
    """Create a config with multiple contracts."""
    return SubgraphConfig(
        name="multi-subgraph",
        network="ethereum",
        output_dir=str(tmp_path / "generated"),
        mappings_mode="auto",
        contracts=[
            ContractConfig(
                name="TokenA",
                address="0x1111111111111111111111111111111111111111",
                start_block=1000,
                abi_path="TokenA.json",
            ),
            ContractConfig(
                name="TokenB",
                address="0x2222222222222222222222222222222222222222",
                start_block=2000,
                abi_path="TokenB.json",
            ),
        ],
    )


class TestRenderSchemaWithAbi:
    """Tests for schema rendering with ABI data."""
    
    def test_generates_entity_from_event(self, sample_config):
        """Test that entity is generated from ABI event."""
        abi_map = {"TestToken": TRANSFER_ABI}
        
        schema = render_schema(sample_config, abi_map)
        
        # Check entity is named after event
        assert "type Transfer @entity" in schema
    
    def test_entity_has_event_params(self, sample_config):
        """Test that entity has fields for event parameters."""
        abi_map = {"TestToken": TRANSFER_ABI}
        
        schema = render_schema(sample_config, abi_map)
        
        # Check parameter fields exist (camelCase)
        assert "from: Bytes!" in schema
        assert "to: Bytes!" in schema
        assert "value: BigInt!" in schema
    
    def test_entity_has_metadata_fields(self, sample_config):
        """Test that entity has standard metadata fields."""
        abi_map = {"TestToken": TRANSFER_ABI}
        
        schema = render_schema(sample_config, abi_map)
        
        assert "blockNumber: BigInt!" in schema
        assert "blockTimestamp: BigInt!" in schema
        assert "transactionHash: Bytes!" in schema
    
    def test_entity_has_id_field(self, sample_config):
        """Test that entity has required ID field."""
        abi_map = {"TestToken": TRANSFER_ABI}
        
        schema = render_schema(sample_config, abi_map)
        
        assert "id: ID!" in schema
    
    def test_generates_multiple_entities_from_multiple_events(self, sample_config):
        """Test that multiple events generate multiple entities."""
        abi_map = {"TestToken": MULTI_EVENT_ABI}
        
        schema = render_schema(sample_config, abi_map)
        
        assert "type Transfer @entity" in schema
        assert "type Approval @entity" in schema
    
    def test_handles_various_solidity_types(self, sample_config):
        """Test that various Solidity types are correctly mapped."""
        abi_map = {"TestToken": COMPLEX_EVENT_ABI}
        
        schema = render_schema(sample_config, abi_map)
        
        # uint256 -> BigInt
        assert "id: BigInt!" in schema
        # address -> Bytes
        assert "sender: Bytes!" in schema
        # bool -> Boolean
        assert "flag: Boolean!" in schema
        # bytes32 -> Bytes
        assert "data: Bytes!" in schema
        # string -> String
        assert "message: String!" in schema


class TestRenderSchemaWithMultipleContracts:
    """Tests for schema with multiple contracts."""
    
    def test_generates_entities_for_all_contracts(self, multi_contract_config):
        """Test that entities are generated for all contracts with ABIs."""
        abi_map = {
            "TokenA": TRANSFER_ABI,
            "TokenB": MULTI_EVENT_ABI,
        }
        
        schema = render_schema(multi_contract_config, abi_map)
        
        # TokenA has Transfer event
        # TokenB has Transfer and Approval events
        # Note: Transfer appears twice but with same definition
        assert "type Transfer @entity" in schema
        assert "type Approval @entity" in schema


class TestRenderSchemaWithoutAbi:
    """Tests for schema rendering without ABI data."""
    
    def test_generates_placeholder_without_abi_map(self, sample_config):
        """Test that placeholder entity is generated without ABI map."""
        schema = render_schema(sample_config, None)
        
        # Should have placeholder entity
        assert "type TestTokenEvent @entity" in schema
    
    def test_generates_placeholder_with_empty_abi_map(self, sample_config):
        """Test that placeholder entity is generated with empty ABI map."""
        schema = render_schema(sample_config, {})
        
        assert "type TestTokenEvent @entity" in schema
    
    def test_generates_placeholder_for_missing_contract(self, multi_contract_config):
        """Test that placeholder is used for contracts without ABI."""
        # Only provide ABI for TokenA
        abi_map = {"TokenA": TRANSFER_ABI}
        
        schema = render_schema(multi_contract_config, abi_map)
        
        # TokenA should have Transfer entity
        assert "type Transfer @entity" in schema
        # TokenB should have placeholder
        assert "type TokenBEvent @entity" in schema


class TestGetAllEntitiesForContract:
    """Tests for get_all_entities_for_contract function."""
    
    def test_returns_entity_names_from_abi(self):
        """Test that entity names are extracted from ABI."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=0,
            abi_path="test.json",
        )
        
        entities = get_all_entities_for_contract(contract, MULTI_EVENT_ABI)
        
        assert "Transfer" in entities
        assert "Approval" in entities
        assert len(entities) == 2
    
    def test_returns_placeholder_without_abi(self):
        """Test that placeholder entity is returned without ABI."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=0,
            abi_path="test.json",
        )
        
        entities = get_all_entities_for_contract(contract, None)
        
        assert entities == ["TestTokenEvent"]
    
    def test_returns_placeholder_with_no_events_in_abi(self):
        """Test that placeholder is returned if ABI has no events."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=0,
            abi_path="test.json",
        )
        
        # ABI with only functions, no events
        abi_no_events = [
            {
                "type": "function",
                "name": "transfer",
                "inputs": [],
                "outputs": [],
            }
        ]
        
        entities = get_all_entities_for_contract(contract, abi_no_events)
        
        assert entities == ["TestTokenEvent"]

